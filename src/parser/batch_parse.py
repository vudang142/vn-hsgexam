"""
VN-HSGExam — Batch Parser
=========================
Parse all 48 .txt files (4 subjects × 6 years × 2 files) into one JSON dataset
plus a per-file validation report.

Expected directory layout (configurable via --input-dir):

    <input-dir>/
        ques_history_2019.txt
        ques_history_2020.txt
        ...
        ques_biology_2024.txt
        ans_history_2019.txt
        ...
        ans_biology_2024.txt

Output:
    <output-dir>/
        vn_hsgexam_all.json       # all ~815 questions, one big JSON array
        vn_hsgexam_usable.json    # only is_usable=true (~600 — will subset to Tier 1 later)
        parse_report.json         # per-file stats + any issues
        parse_report.md           # human-readable summary

Usage:
    python batch_parse.py --input-dir /path/to/uploads --output-dir ./data

Or in Colab:
    !python batch_parse.py --input-dir /content/drive/MyDrive/vnhsg/raw \\
                           --output-dir /content/drive/MyDrive/vnhsg/parsed
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path
from collections import Counter, defaultdict

from vn_hsgexam_parser import parse_pair, SUBJECT_RANGES

SUBJECTS = ["history", "geography", "civics", "biology"]
YEARS = [2019, 2020, 2021, 2022, 2023, 2024]


def find_pair(input_dir: Path, subject: str, year: int) -> tuple[Path, Path] | None:
    """Locate ques_/ans_ pair for a (subject, year). Returns None if missing."""
    qp = input_dir / f"ques_{subject}_{year}.txt"
    ap = input_dir / f"ans_{subject}_{year}.txt"
    if qp.exists() and ap.exists():
        return qp, ap
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input-dir", required=True, type=Path,
                    help="Directory containing the 48 .txt files")
    ap.add_argument("--output-dir", required=True, type=Path,
                    help="Where to write JSON outputs and reports")
    ap.add_argument("--strict", action="store_true",
                    help="Exit non-zero if any file has validation issues")
    args = ap.parse_args()

    args.output_dir.mkdir(parents=True, exist_ok=True)

    all_questions = []
    report = {
        "input_dir": str(args.input_dir),
        "files": {},     # "subject_year" -> {parsed_count, usable_count, issues, ...}
        "missing": [],
    }
    total_issues = 0

    for subject in SUBJECTS:
        for year in YEARS:
            key = f"{subject}_{year}"
            pair = find_pair(args.input_dir, subject, year)
            if pair is None:
                report["missing"].append(key)
                print(f"  [MISSING] {key}")
                continue

            qp, ans_p = pair
            try:
                questions, issues = parse_pair(qp, ans_p, subject, year)
            except Exception as e:
                report["files"][key] = {"error": str(e)}
                total_issues += 1
                print(f"  [ERROR] {key}: {e}")
                continue

            usable = sum(1 for q in questions if q.is_usable)
            tag_counts = Counter(q.exclusion_tag for q in questions if q.exclusion_tag)

            report["files"][key] = {
                "parsed_count": len(questions),
                "usable_count": usable,
                "excluded_count": len(questions) - usable,
                "excluded_tags": dict(tag_counts),
                "issues": issues,
            }
            total_issues += len(issues)
            all_questions.extend(questions)

            status = "✓" if not issues else f"⚠ ({len(issues)} issues)"
            print(f"  [{status}] {key}: {len(questions)} parsed, "
                  f"{usable} usable, {len(questions)-usable} excluded")
            for iss in issues:
                print(f"      - {iss}")

    # Compute overall stats
    stats = compute_stats(all_questions)
    report["overall"] = stats

    # Dump JSON files
    all_json = [asdict(q) for q in all_questions]
    usable_json = [asdict(q) for q in all_questions if q.is_usable]

    out_all = args.output_dir / "vn_hsgexam_all.json"
    out_usable = args.output_dir / "vn_hsgexam_usable.json"
    out_report_json = args.output_dir / "parse_report.json"
    out_report_md = args.output_dir / "parse_report.md"

    out_all.write_text(json.dumps(all_json, ensure_ascii=False, indent=2), encoding="utf-8")
    out_usable.write_text(json.dumps(usable_json, ensure_ascii=False, indent=2), encoding="utf-8")
    out_report_json.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    out_report_md.write_text(render_markdown_report(report, stats), encoding="utf-8")

    print()
    print("=" * 60)
    print(f"  Total parsed     : {len(all_questions)}")
    print(f"  Total usable     : {sum(1 for q in all_questions if q.is_usable)}")
    print(f"  Total excluded   : {sum(1 for q in all_questions if not q.is_usable)}")
    print(f"  Missing files    : {len(report['missing'])}")
    print(f"  Files with issues: {total_issues}")
    print(f"  Output dir       : {args.output_dir}")
    print("=" * 60)

    if args.strict and total_issues:
        sys.exit(1)


def compute_stats(questions) -> dict:
    """Aggregate statistics suitable for paper Table 1."""
    by_subject = defaultdict(list)
    for q in questions:
        by_subject[q.subject].append(q)

    out = {"by_subject": {}, "by_year": {}, "by_subject_year": {}}

    for subj, qs in by_subject.items():
        usable = [q for q in qs if q.is_usable]
        diffs = Counter(q.difficulty for q in usable)
        ans = Counter(q.answer for q in usable if q.answer)
        out["by_subject"][subj] = {
            "total": len(qs),
            "usable": len(usable),
            "excluded": len(qs) - len(usable),
            "difficulty": dict(diffs),
            "answer_dist": dict(ans),
            "excluded_tags": dict(Counter(q.exclusion_tag for q in qs if q.exclusion_tag)),
        }

    by_year = defaultdict(list)
    for q in questions:
        by_year[q.year].append(q)
    for yr, qs in by_year.items():
        usable = [q for q in qs if q.is_usable]
        out["by_year"][str(yr)] = {"total": len(qs), "usable": len(usable)}

    for subj in SUBJECTS:
        for yr in YEARS:
            qs = [q for q in questions if q.subject == subj and q.year == yr]
            if qs:
                out["by_subject_year"][f"{subj}_{yr}"] = {
                    "total": len(qs),
                    "usable": sum(1 for q in qs if q.is_usable),
                }

    return out


def render_markdown_report(report: dict, stats: dict) -> str:
    lines = ["# VN-HSGExam Parse Report\n"]
    lines.append(f"- Input directory: `{report['input_dir']}`")
    lines.append(f"- Missing files: {len(report['missing'])}")
    if report["missing"]:
        for m in report["missing"]:
            lines.append(f"    - {m}")
    lines.append("")

    lines.append("## Per-Subject Summary\n")
    lines.append("| Subject | Total | Usable | Excluded | Tags |")
    lines.append("|---|---:|---:|---:|---|")
    for subj in SUBJECTS:
        s = stats["by_subject"].get(subj)
        if not s:
            continue
        tags = ", ".join(f"{k}:{v}" for k, v in s.get("excluded_tags", {}).items()) or "—"
        lines.append(f"| {subj} | {s['total']} | {s['usable']} | {s['excluded']} | {tags} |")

    lines.append("\n## Per-File Status\n")
    lines.append("| File | Parsed | Usable | Issues |")
    lines.append("|---|---:|---:|---|")
    for key, info in sorted(report["files"].items()):
        if "error" in info:
            lines.append(f"| {key} | ERROR | — | {info['error']} |")
        else:
            iss = "; ".join(info["issues"]) if info["issues"] else "✓"
            lines.append(f"| {key} | {info['parsed_count']} | {info['usable_count']} | {iss} |")

    lines.append("\n## Difficulty Distribution (usable only)\n")
    lines.append("| Subject | Easy | Medium | Hard |")
    lines.append("|---|---:|---:|---:|")
    for subj in SUBJECTS:
        s = stats["by_subject"].get(subj)
        if not s:
            continue
        d = s["difficulty"]
        lines.append(f"| {subj} | {d.get('easy',0)} | {d.get('medium',0)} | {d.get('hard',0)} |")

    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    main()
