"""
VN-HSGExam — Tier 1 Sampling
============================
Sample 129 questions per subject from the full usable set, stratified by
difficulty (preserving each subject's natural distribution) and balanced
across years (~21-22 questions per year).

Strategy:
- For each (subject, difficulty) cell, compute the target N proportional to
  the subject's full difficulty distribution.
- Within each cell, distribute the target N across 6 years as evenly as
  possible. If a (subject, difficulty, year) bucket doesn't have enough
  questions, take all available and let other years compensate.
- All randomness uses a fixed seed for reproducibility.

Geography special case: only 129 usable, so it takes ALL of them.

Outputs (in --output-dir):
    tier1_balanced.json    # 516 questions sampled for Tier 1
    tier2_extended.json    # remaining ~342 usable questions for robustness
    tier1_report.md        # human-readable composition report
    tier1_report.json      # machine-readable composition
"""
from __future__ import annotations

import argparse
import json
import random
from collections import Counter, defaultdict
from pathlib import Path

# Fixed seed for reproducibility — DO NOT CHANGE across runs.
SAMPLING_SEED = 42

SUBJECTS = ["history", "geography", "civics", "biology"]
DIFFICULTIES = ["easy", "medium", "hard"]
YEARS = [2019, 2020, 2021, 2022, 2023, 2024]

# Target per subject (set by the smallest usable count — Geography: 129)
TARGET_PER_SUBJECT = 129


def load_questions(path: Path) -> list[dict]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def group_by(questions: list[dict], *keys: str) -> dict:
    """Group questions by tuple of key values."""
    grouped = defaultdict(list)
    for q in questions:
        k = tuple(q[key] for key in keys)
        grouped[k].append(q)
    return dict(grouped)


def compute_difficulty_targets(
    subject_questions: list[dict], target_total: int
) -> dict[str, int]:
    """Largest-remainder allocation: preserve difficulty proportions when
    rounding to integers that sum to exactly target_total.

    Why not naive rounding? Naive rounding can sum to target_total ± 1-2,
    and we want exact 129. Largest-remainder method handles this cleanly.
    """
    total = len(subject_questions)
    if total == target_total:
        # Geography case: take all.
        return dict(Counter(q["difficulty"] for q in subject_questions))

    raw_counts = Counter(q["difficulty"] for q in subject_questions)
    proportions = {d: raw_counts.get(d, 0) / total for d in DIFFICULTIES}

    # Floor allocation first
    floored = {d: int(proportions[d] * target_total) for d in DIFFICULTIES}
    assigned = sum(floored.values())
    remaining = target_total - assigned

    # Distribute leftovers to difficulties with largest fractional remainders
    fractionals = sorted(
        DIFFICULTIES,
        key=lambda d: (proportions[d] * target_total) - floored[d],
        reverse=True,
    )
    for d in fractionals[:remaining]:
        floored[d] += 1

    # Sanity check: targets must not exceed available counts
    for d in DIFFICULTIES:
        if floored[d] > raw_counts.get(d, 0):
            # Shift the overflow to a difficulty that has spare capacity
            overflow = floored[d] - raw_counts[d]
            floored[d] = raw_counts[d]
            for other in DIFFICULTIES:
                if other == d:
                    continue
                spare = raw_counts.get(other, 0) - floored[other]
                if spare > 0:
                    take = min(spare, overflow)
                    floored[other] += take
                    overflow -= take
                    if overflow == 0:
                        break
            if overflow > 0:
                raise ValueError(
                    f"Cannot allocate {target_total} from subject with "
                    f"counts {dict(raw_counts)}"
                )

    return floored


def sample_for_subject(
    subject_questions: list[dict],
    target_total: int,
    rng: random.Random,
) -> tuple[list[dict], dict]:
    """Sample `target_total` questions from one subject. Returns (selected, report)."""
    diff_targets = compute_difficulty_targets(subject_questions, target_total)
    selected: list[dict] = []
    composition = {}

    for diff in DIFFICULTIES:
        cell_target = diff_targets[diff]
        if cell_target == 0:
            composition[diff] = {"target": 0, "selected": 0, "by_year": {}}
            continue

        cell_pool = [q for q in subject_questions if q["difficulty"] == diff]
        # Balance by year: distribute cell_target across 6 years as evenly as possible.
        # Largest-remainder again, this time on equal proportions per year.
        per_year_target = _allocate_by_year(cell_pool, cell_target)

        cell_selected = []
        for year, n in per_year_target.items():
            year_pool = [q for q in cell_pool if q["year"] == year]
            if len(year_pool) < n:
                # Year has fewer than target; take all, redistribute later
                cell_selected.extend(year_pool)
            else:
                sampled = rng.sample(year_pool, n)
                cell_selected.extend(sampled)

        # If under-allocated (some year was short), top up from remaining pool
        shortage = cell_target - len(cell_selected)
        if shortage > 0:
            already_ids = {q["question_id"] for q in cell_selected}
            remaining = [q for q in cell_pool if q["question_id"] not in already_ids]
            top_up = rng.sample(remaining, min(shortage, len(remaining)))
            cell_selected.extend(top_up)

        selected.extend(cell_selected)
        composition[diff] = {
            "target": cell_target,
            "selected": len(cell_selected),
            "by_year": dict(Counter(q["year"] for q in cell_selected)),
        }

    return selected, composition


def _allocate_by_year(cell_pool: list[dict], cell_target: int) -> dict[int, int]:
    """Distribute cell_target across YEARS as evenly as possible, respecting
    available counts per year.
    """
    available = Counter(q["year"] for q in cell_pool)
    n_years = len(YEARS)
    base = cell_target // n_years
    rem = cell_target % n_years

    # Start with equal share
    allocation = {y: min(base, available.get(y, 0)) for y in YEARS}

    # Distribute remainder to years with the most spare capacity
    spare_by_year = sorted(
        YEARS,
        key=lambda y: available.get(y, 0) - allocation[y],
        reverse=True,
    )
    for y in spare_by_year[:rem]:
        if allocation[y] < available.get(y, 0):
            allocation[y] += 1

    # Compensate any year that couldn't meet `base` by giving extra to others
    deficit = cell_target - sum(allocation.values())
    while deficit > 0:
        added = False
        for y in spare_by_year:
            if allocation[y] < available.get(y, 0):
                allocation[y] += 1
                deficit -= 1
                added = True
                if deficit == 0:
                    break
        if not added:
            # Truly cannot allocate more — pool is exhausted
            break

    return allocation


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--input", required=True, type=Path,
        help="Path to vn_hsgexam_usable.json"
    )
    ap.add_argument(
        "--output-dir", required=True, type=Path,
        help="Where to write tier1 / tier2 / reports"
    )
    args = ap.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    questions = load_questions(args.input)
    print(f"Loaded {len(questions)} usable questions from {args.input}")

    rng = random.Random(SAMPLING_SEED)

    by_subject = group_by(questions, "subject")
    tier1: list[dict] = []
    full_composition = {}

    print(f"\nSampling Tier 1 (target {TARGET_PER_SUBJECT} per subject, seed={SAMPLING_SEED}):")
    for subj in SUBJECTS:
        subj_pool = by_subject.get((subj,), [])
        if len(subj_pool) < TARGET_PER_SUBJECT:
            raise ValueError(
                f"{subj}: only {len(subj_pool)} usable; need {TARGET_PER_SUBJECT}"
            )
        # Sort pool by question_id BEFORE sampling — RNG order then depends only on seed,
        # not on JSON insertion order.
        subj_pool = sorted(subj_pool, key=lambda q: q["question_id"])
        selected, comp = sample_for_subject(subj_pool, TARGET_PER_SUBJECT, rng)
        tier1.extend(selected)
        full_composition[subj] = comp
        print(f"  {subj}: {len(selected)} selected")
        for diff in DIFFICULTIES:
            c = comp[diff]
            print(f"    {diff:7s}: {c['selected']}/{c['target']} "
                  f"by_year={c['by_year']}")

    # Tier 2 = remaining usable not in Tier 1
    tier1_ids = {q["question_id"] for q in tier1}
    tier2 = [q for q in questions if q["question_id"] not in tier1_ids]

    # Sort outputs deterministically
    tier1_sorted = sorted(tier1, key=lambda q: q["question_id"])
    tier2_sorted = sorted(tier2, key=lambda q: q["question_id"])

    out_t1 = args.output_dir / "tier1_balanced.json"
    out_t2 = args.output_dir / "tier2_extended.json"
    out_report_md = args.output_dir / "tier1_report.md"
    out_report_json = args.output_dir / "tier1_report.json"

    out_t1.write_text(json.dumps(tier1_sorted, ensure_ascii=False, indent=2),
                      encoding="utf-8")
    out_t2.write_text(json.dumps(tier2_sorted, ensure_ascii=False, indent=2),
                      encoding="utf-8")

    report = {
        "seed": SAMPLING_SEED,
        "target_per_subject": TARGET_PER_SUBJECT,
        "tier1_total": len(tier1),
        "tier2_total": len(tier2),
        "composition": full_composition,
    }
    out_report_json.write_text(json.dumps(report, ensure_ascii=False, indent=2),
                               encoding="utf-8")
    out_report_md.write_text(render_markdown(report), encoding="utf-8")

    print()
    print("=" * 60)
    print(f"  Tier 1 (balanced)  : {len(tier1)} questions")
    print(f"  Tier 2 (extended)  : {len(tier2)} questions")
    print(f"  Seed               : {SAMPLING_SEED}")
    print(f"  Output dir         : {args.output_dir}")
    print("=" * 60)


def render_markdown(report: dict) -> str:
    lines = ["# VN-HSGExam Tier 1 Sampling Report\n"]
    lines.append(f"- Random seed: `{report['seed']}` (fixed for reproducibility)")
    lines.append(f"- Target per subject: {report['target_per_subject']}")
    lines.append(f"- Tier 1 total: {report['tier1_total']}")
    lines.append(f"- Tier 2 total: {report['tier2_total']}")
    lines.append("")

    lines.append("## Composition\n")
    lines.append("| Subject | Easy | Medium | Hard | Total |")
    lines.append("|---|---:|---:|---:|---:|")
    for subj in SUBJECTS:
        c = report["composition"][subj]
        e = c["easy"]["selected"]
        m = c["medium"]["selected"]
        h = c["hard"]["selected"]
        lines.append(f"| {subj} | {e} | {m} | {h} | {e+m+h} |")

    lines.append("\n## Per-Subject × Difficulty × Year\n")
    for subj in SUBJECTS:
        lines.append(f"\n### {subj}\n")
        lines.append("| Difficulty | " + " | ".join(str(y) for y in YEARS) + " | Total |")
        lines.append("|---|" + "---:|" * (len(YEARS) + 1))
        for diff in DIFFICULTIES:
            row = report["composition"][subj][diff]
            by_year = row["by_year"]
            cells = [str(by_year.get(y, 0)) for y in YEARS]
            lines.append(f"| {diff} | " + " | ".join(cells) + f" | {row['selected']} |")

    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    main()
