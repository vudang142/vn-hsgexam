"""
VN-HSGExam Parser
=================
Convert raw .txt exam files (question + answer key) into structured JSON.

Input file conventions (per project spec):
- Question file:  ques_{subject}_{year}.txt
- Answer file:    ans_{subject}_{year}.txt
- Subjects: history, geography, civics, biology
- Question number ranges:
    history    : 1-40
    geography  : 41-80
    civics     : 81-120
    biology    : 81-120

Stem format:
    Câu N: <stem text, possibly multi-line>
    A. <choice A>
    B. <choice B>
    C. <choice C>
    D. <choice D>
    [LOẠI: TAG]   <-- optional, only on excluded questions

Footer after the last question:
    ===
    ...summary...
    ===

Difficulty heuristic (per MoET convention - first 50% easy, next 25% medium, last 25% hard):
    history    (1-40)   : 1-20 easy, 21-30 medium, 31-40 hard
    geography  (41-80)  : 41-60 easy, 61-70 medium, 71-80 hard
    civics     (81-120) : 81-100 easy, 101-110 medium, 111-120 hard
    biology    (81-120) : 81-100 easy, 101-110 medium, 111-120 hard
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import Optional


# ---------- Configuration ----------

SUBJECT_RANGES = {
    "history":   (1,   40),
    "geography": (41,  80),
    "civics":    (81, 120),
    "biology":   (81, 120),
}

# (low_max, mid_max). question_number <= low_max -> easy; <= mid_max -> medium; else hard.
DIFFICULTY_BUCKETS = {
    "history":   (20, 30),
    "geography": (60, 70),
    "civics":    (100, 110),
    "biology":   (100, 110),
}

VALID_TAGS = {"ATLAS", "HÌNH", "PHẢ HỆ", "BẢNG", "ĐỒ THỊ"}

# Aliases: các tag tương đương sẽ được normalize về canonical form (key của dict).
# Khi parser gặp tag thuộc set values, nó sẽ đổi thành key.
# Tag canonical "ĐỒ THỊ" bao gồm cả "BIỂU ĐỒ" (đồng nghĩa trong tiếng Việt).
TAG_ALIASES = {
    "ĐỒ THỊ": {"BIỂU ĐỒ"},
    "HÌNH":   {"HINH", "ẢNH", "HÌNH ẢNH"},
    "PHẢ HỆ": {"PHA HE", "SƠ ĐỒ PHẢ HỆ"},
    "BẢNG":   {"BANG", "BẢNG SỐ LIỆU"},
    "ATLAS":  {"ÁT-LÁT", "AT LAT"},
}


# ---------- Regex patterns ----------

# Câu N:  (start of new question). Number captured.
RE_QUESTION_START = re.compile(r"^Câu\s+(\d+)\s*:\s*(.*)$")

# A./B./C./D. choice marker. Letter captured, content captured.
RE_CHOICE = re.compile(r"^([ABCD])\.\s*(.*)$")

# [LOẠI: TAG]  exclusion marker. Tag captured (raw, may contain spaces).
RE_EXCLUSION = re.compile(r"^\[LOẠI:\s*([^\]]+)\]\s*$")

# Footer delimiter
RE_FOOTER = re.compile(r"^=+\s*$")

# Answer-key line: "N. X" or "N.X" or "N: X" where X is A|B|C|D
RE_ANSWER = re.compile(r"^\s*(\d+)\s*[.:]\s*([ABCD])\s*$")


# ---------- Data model ----------

@dataclass
class Question:
    question_id: str
    subject: str
    year: int
    question_number: int
    stem: str
    choices: dict           # {"A": "...", "B": "...", "C": "...", "D": "..."}
    answer: Optional[str]   # "A"|"B"|"C"|"D"|None (None if no answer key yet)
    is_usable: bool
    exclusion_tag: Optional[str]
    difficulty: str         # "easy" | "medium" | "hard"
    metadata: dict = field(default_factory=dict)


# ---------- Helpers ----------

def difficulty_for(subject: str, qnum: int) -> str:
    low_max, mid_max = DIFFICULTY_BUCKETS[subject]
    if qnum <= low_max:
        return "easy"
    if qnum <= mid_max:
        return "medium"
    return "hard"


def normalize_tag(raw_tag: str) -> str:
    """Normalize whitespace, uppercase, then resolve aliases to canonical form.

    Examples:
        'BIỂU ĐỒ'  -> 'ĐỒ THỊ' (alias)
        'biểu đồ'  -> 'ĐỒ THỊ' (alias + case)
        'ĐỒ THỊ'   -> 'ĐỒ THỊ' (no change, already canonical)
        'ATLAS'    -> 'ATLAS'  (canonical)
    """
    normalized = re.sub(r"\s+", " ", raw_tag).strip().upper()
    # Resolve aliases: if normalized matches any alias, return its canonical form.
    for canonical, aliases in TAG_ALIASES.items():
        if normalized == canonical or normalized in aliases:
            return canonical
    return normalized  # No alias matched; return as-is (will fail VALID_TAGS check if unknown)


# ---------- Answer-key parser ----------

def parse_answer_key(path: Path) -> dict[int, str]:
    """Return {question_number: 'A'|'B'|'C'|'D'}."""
    answers: dict[int, str] = {}
    with open(path, "r", encoding="utf-8") as f:
        for lineno, raw in enumerate(f, start=1):
            line = raw.strip()
            if not line:
                continue
            m = RE_ANSWER.match(line)
            if not m:
                raise ValueError(
                    f"{path.name}:{lineno}: cannot parse answer line: {raw!r}"
                )
            qnum = int(m.group(1))
            letter = m.group(2)
            if qnum in answers:
                raise ValueError(
                    f"{path.name}:{lineno}: duplicate answer for question {qnum}"
                )
            answers[qnum] = letter
    return answers


# ---------- Question parser ----------

class _QuestionBuffer:
    """Accumulates lines for one question while we walk the file."""

    def __init__(self, qnum: int, first_stem_line: str):
        self.qnum = qnum
        self.stem_lines: list[str] = [first_stem_line] if first_stem_line else []
        self.choices: dict[str, list[str]] = {}     # letter -> list of lines
        self._current_choice: Optional[str] = None
        self.exclusion_tag: Optional[str] = None

    def add_line(self, line: str) -> None:
        # 1. Exclusion tag — always belongs to whole question, not a choice.
        m_tag = RE_EXCLUSION.match(line)
        if m_tag:
            self.exclusion_tag = normalize_tag(m_tag.group(1))
            self._current_choice = None
            return

        # 2. Choice marker?
        m_choice = RE_CHOICE.match(line)
        if m_choice:
            letter = m_choice.group(1)
            content = m_choice.group(2)
            self.choices[letter] = [content] if content else []
            self._current_choice = letter
            return

        # 3. Continuation line. Belongs to current choice if any, else stem.
        if self._current_choice is not None:
            self.choices[self._current_choice].append(line)
        else:
            self.stem_lines.append(line)

    def finalize(self, subject: str, year: int, answer: Optional[str]) -> Question:
        if self.qnum is None:
            raise ValueError("Question buffer has no number")

        # Validate choice completeness
        missing = [c for c in "ABCD" if c not in self.choices]
        if missing:
            raise ValueError(
                f"Question {self.qnum}: missing choices {missing}"
            )

        stem = "\n".join(s for s in self.stem_lines).strip()
        choices = {
            letter: " ".join(parts).strip()
            for letter, parts in self.choices.items()
        }

        if self.exclusion_tag is not None and self.exclusion_tag not in VALID_TAGS:
            raise ValueError(
                f"Question {self.qnum}: unknown exclusion tag {self.exclusion_tag!r}"
            )

        is_usable = self.exclusion_tag is None

        return Question(
            question_id=f"{subject}_{year}_q{self.qnum}",
            subject=subject,
            year=year,
            question_number=self.qnum,
            stem=stem,
            choices=choices,
            answer=answer,
            is_usable=is_usable,
            exclusion_tag=self.exclusion_tag,
            difficulty=difficulty_for(subject, self.qnum),
            metadata={
                "stem_char_length": len(stem),
                "stem_line_count": len(self.stem_lines),
            },
        )


def parse_question_file(
    path: Path, subject: str, year: int, answers: dict[int, str]
) -> list[Question]:
    """Walk the question file line-by-line and produce a list of Question objects."""
    questions: list[Question] = []
    current: Optional[_QuestionBuffer] = None
    in_footer = False

    def flush():
        if current is not None:
            ans = answers.get(current.qnum)
            questions.append(current.finalize(subject, year, ans))

    with open(path, "r", encoding="utf-8") as f:
        for lineno, raw in enumerate(f, start=1):
            line = raw.rstrip("\n").rstrip("\r")
            stripped = line.strip()

            # Footer toggle: first '===' opens footer, we stop parsing questions.
            if RE_FOOTER.match(stripped):
                flush()
                current = None
                in_footer = True
                continue
            if in_footer:
                continue

            # Blank lines: just terminate "current choice" continuation.
            # We do NOT flush — Câu N: marker is the only flush trigger.
            if not stripped:
                if current is not None:
                    current._current_choice = None
                continue

            # New question?
            m_q = RE_QUESTION_START.match(stripped)
            if m_q:
                flush()
                qnum = int(m_q.group(1))
                first_stem = m_q.group(2).strip()
                current = _QuestionBuffer(qnum, first_stem)
                continue

            # Lines belonging to current question
            if current is None:
                # Stray line before first question — probably exam header. Skip.
                continue
            try:
                current.add_line(stripped)
            except Exception as e:
                raise ValueError(f"{path.name}:{lineno}: {e}") from e

    # End of file
    flush()
    return questions


# ---------- Validators ----------

def validate_question_set(
    questions: list[Question],
    subject: str,
    year: int,
    answers: dict[int, str],
) -> list[str]:
    """Return list of validation warnings/errors (empty list = all good)."""
    issues: list[str] = []
    low, high = SUBJECT_RANGES[subject]
    expected = set(range(low, high + 1))
    got = {q.question_number for q in questions}

    missing = expected - got
    extra = got - expected
    if missing:
        issues.append(f"Missing question numbers: {sorted(missing)}")
    if extra:
        issues.append(f"Unexpected question numbers: {sorted(extra)}")

    # Answer-key coverage
    ans_missing = expected - set(answers.keys())
    ans_extra = set(answers.keys()) - expected
    if ans_missing:
        issues.append(f"Answer key missing for: {sorted(ans_missing)}")
    if ans_extra:
        issues.append(f"Answer key has extra entries: {sorted(ans_extra)}")

    # Per-question checks
    for q in questions:
        for letter in "ABCD":
            if letter not in q.choices or not q.choices[letter]:
                issues.append(f"Q{q.question_number}: empty/missing choice {letter}")
        if q.is_usable and q.answer is None:
            issues.append(f"Q{q.question_number}: usable but no answer in key")

    return issues


# ---------- Top-level driver ----------

def parse_pair(
    question_path: Path,
    answer_path: Path,
    subject: str,
    year: int,
) -> tuple[list[Question], list[str]]:
    """Parse one (question_file, answer_file) pair. Return (questions, issues)."""
    answers = parse_answer_key(answer_path)
    questions = parse_question_file(question_path, subject, year, answers)
    issues = validate_question_set(questions, subject, year, answers)
    return questions, issues


def questions_to_json(questions: list[Question]) -> list[dict]:
    return [asdict(q) for q in questions]


# ---------- CLI demo ----------

if __name__ == "__main__":
    import sys

    if len(sys.argv) != 5:
        print("Usage: python vn_hsgexam_parser.py <ques.txt> <ans.txt> <subject> <year>")
        sys.exit(2)

    qp, ap, subj, yr = sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4])
    questions, issues = parse_pair(Path(qp), Path(ap), subj, yr)

    print(f"Parsed {len(questions)} questions from {qp}")
    print(f"Usable: {sum(1 for q in questions if q.is_usable)}")
    print(f"Excluded: {sum(1 for q in questions if not q.is_usable)}")

    if issues:
        print("\n--- ISSUES ---")
        for issue in issues:
            print(f"  ! {issue}")
    else:
        print("\nNo issues found.")

    # Dump JSON
    out = json.dumps(questions_to_json(questions), ensure_ascii=False, indent=2)
    print("\n--- FIRST QUESTION (preview) ---")
    print(json.dumps(asdict(questions[0]), ensure_ascii=False, indent=2))
