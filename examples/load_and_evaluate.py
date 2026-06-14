"""Minimal example: load VN-HSGExam Tier 1 and run a single model evaluation.

This script is a self-contained, runnable example showing how to:

  1. Load the Tier 1 dataset (or Tier 2 reserve).
  2. Apply one of four prompting strategies (zero-shot, few-shot, CoT, CoT-stochastic).
  3. Call a model API (Cerebras / Groq) or a local llama.cpp instance.
  4. Parse the predicted letter and write predictions to a JSONL file.

The actual API / local-inference calls are abstracted behind `call_model`, so this
script can be run in a "dry-run" mode that just prints prompts without making
any network calls. This is useful for reviewers who want to verify the data
pipeline without setting up API keys.

Usage:
    # Dry run (no API calls, just prints first 3 prompts)
    python examples/load_and_evaluate.py --dry-run

    # Real run (requires API keys in environment variables)
    python examples/load_and_evaluate.py \\
        --model qwen3-235b \\
        --strategy few_shot \\
        --tier 1 \\
        --output results/predictions_qwen3_fewshot.jsonl
"""

from __future__ import annotations

import argparse
import json
import os
import random
import re
import sys
import time
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Prompt templates
# ---------------------------------------------------------------------------

PROMPT_TEMPLATES = {
    "zero_shot": (
        "Bạn là một học sinh Việt Nam đang làm bài thi trắc nghiệm. "
        "Hãy chọn một đáp án đúng nhất (A, B, C hoặc D) cho câu hỏi dưới đây. "
        "Chỉ trả lời bằng một chữ cái duy nhất.\n\n"
        "Câu hỏi: {stem}\n"
        "A. {A}\n"
        "B. {B}\n"
        "C. {C}\n"
        "D. {D}\n\n"
        "Đáp án:"
    ),
    "few_shot": (
        "Dưới đây là một số ví dụ về câu hỏi trắc nghiệm và đáp án đúng. "
        "Sau đó, hãy trả lời câu hỏi mới bằng một chữ cái duy nhất (A, B, C hoặc D).\n\n"
        "{examples}\n\n"
        "Câu hỏi mới:\n"
        "{stem}\n"
        "A. {A}\n"
        "B. {B}\n"
        "C. {C}\n"
        "D. {D}\n\n"
        "Đáp án:"
    ),
    "cot": (
        "Bạn là một học sinh Việt Nam đang làm bài thi trắc nghiệm. "
        "Hãy suy nghĩ từng bước một cách cẩn thận, sau đó đưa ra đáp án cuối cùng "
        "bằng một chữ cái duy nhất (A, B, C hoặc D) ở dòng cuối cùng theo định dạng:\n"
        "Đáp án: <chữ cái>\n\n"
        "Câu hỏi: {stem}\n"
        "A. {A}\n"
        "B. {B}\n"
        "C. {C}\n"
        "D. {D}\n\n"
        "Lời giải:"
    ),
    "cot_stochastic": (
        "Bạn là một học sinh Việt Nam đang làm bài thi trắc nghiệm. "
        "Hãy suy nghĩ từng bước một cách cẩn thận, sau đó đưa ra đáp án cuối cùng "
        "bằng một chữ cái duy nhất (A, B, C hoặc D) ở dòng cuối cùng theo định dạng:\n"
        "Đáp án: <chữ cái>\n\n"
        "Câu hỏi: {stem}\n"
        "A. {A}\n"
        "B. {B}\n"
        "C. {C}\n"
        "D. {D}\n\n"
        "Lời giải:"
    ),
}


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


def load_tier(data_dir: Path, tier: int) -> list[dict[str, Any]]:
    """Load Tier 1 or Tier 2 from data/processed/."""
    filename = f"tier{['one', 'two'][tier - 1] if False else tier}_balanced.json" \
        if tier == 1 else "tier2_extended.json"

    # Use the correct filename
    if tier == 1:
        path = data_dir / "tier1_balanced.json"
    elif tier == 2:
        path = data_dir / "tier2_extended.json"
    else:
        raise ValueError(f"tier must be 1 or 2, got {tier}")

    if not path.exists():
        raise FileNotFoundError(
            f"Tier {tier} file not found: {path}\n"
            f"Please run the data preparation pipeline first."
        )

    with open(path, encoding="utf-8") as f:
        return json.load(f)


def format_prompt(item: dict[str, Any], strategy: str, examples: list[dict[str, Any]] | None = None) -> str:
    """Format a single prompt for the given item and strategy."""
    template = PROMPT_TEMPLATES[strategy]
    fmt = {
        "stem": item["stem"],
        "A": item["choices"]["A"],
        "B": item["choices"]["B"],
        "C": item["choices"]["C"],
        "D": item["choices"]["D"],
    }

    if strategy == "few_shot":
        if not examples:
            raise ValueError("few_shot strategy requires --n-examples > 0")
        ex_text = "\n\n".join(
            f"Câu hỏi: {ex['stem']}\n"
            f"A. {ex['choices']['A']}\n"
            f"B. {ex['choices']['B']}\n"
            f"C. {ex['choices']['C']}\n"
            f"D. {ex['choices']['D']}\n"
            f"Đáp án: {ex['answer']}"
            for ex in examples
        )
        fmt["examples"] = ex_text

    return template.format(**fmt)


def parse_answer(response: str) -> str | None:
    """Extract a single letter A/B/C/D from the model's response."""
    # Look for "Đáp án: X" pattern first (Vietnamese)
    m = re.search(r"Đáp\s*án[:\s]*([A-D])", response, re.IGNORECASE)
    if m:
        return m.group(1).upper()
    # Look for "Answer: X" pattern (English)
    m = re.search(r"Answer[:\s]*([A-D])", response, re.IGNORECASE)
    if m:
        return m.group(1).upper()
    # Fallback: last single uppercase letter A-D
    matches = re.findall(r"\b([A-D])\b", response)
    if matches:
        return matches[-1].upper()
    return None


def call_model(prompt: str, model: str, strategy: str, dry_run: bool = False) -> str:
    """Call the model API. In dry-run mode, just return a fake response."""
    if dry_run:
        # Simulate a model response for testing
        return f"[DRY-RUN response for model={model}, strategy={strategy}]\nĐáp án: A"

    # In real run, this would call Cerebras / Groq / llama.cpp
    # See src/inference/llm_client.py for the actual implementation.
    raise NotImplementedError(
        "Real model calls are not implemented in this minimal example. "
        "See src/inference/llm_client.py for the full client, or use --dry-run."
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a minimal evaluation on VN-HSGExam.")
    parser.add_argument("--data-dir", type=Path, default=Path("data/processed"),
                        help="Path to the data/processed directory.")
    parser.add_argument("--tier", type=int, choices=[1, 2], default=1,
                        help="Which tier to evaluate (1 or 2).")
    parser.add_argument("--model", type=str, default="qwen3-235b",
                        choices=["vistral-7b", "llama-3.1-8b", "gpt-oss-120b", "qwen3-235b"],
                        help="Model to evaluate.")
    parser.add_argument("--strategy", type=str, default="zero_shot",
                        choices=list(PROMPT_TEMPLATES.keys()),
                        help="Prompting strategy.")
    parser.add_argument("--n-examples", type=int, default=5,
                        help="Number of few-shot examples (only for few_shot strategy).")
    parser.add_argument("--limit", type=int, default=None,
                        help="Limit the number of items to evaluate (for quick testing).")
    parser.add_argument("--output", type=Path, default=None,
                        help="Output JSONL file. If not specified, prints to stdout.")
    parser.add_argument("--seed", type=int, default=42,
                        help="Random seed for few-shot example selection.")
    parser.add_argument("--dry-run", action="store_true",
                        help="Don't make real API calls; just print prompts.")
    args = parser.parse_args()

    # Load items
    items = load_tier(args.data_dir, args.tier)
    if args.limit:
        items = items[: args.limit]

    # Few-shot examples: sample from a separate pool (Tier 2 in production)
    examples: list[dict[str, Any]] = []
    if args.strategy == "few_shot":
        try:
            tier2 = load_tier(args.data_dir, 2)
            rng = random.Random(args.seed)
            examples = rng.sample(tier2, k=min(args.n_examples, len(tier2)))
        except FileNotFoundError:
            print("WARNING: Tier 2 not found, few-shot examples will be empty.", file=sys.stderr)

    # Evaluate
    predictions = []
    n_correct = 0
    n_total = 0
    n_parse_failed = 0
    start_time = time.time()

    for i, item in enumerate(items):
        prompt = format_prompt(item, args.strategy, examples)
        response = call_model(prompt, args.model, args.strategy, dry_run=args.dry_run)
        parsed = parse_answer(response)
        is_correct = (parsed is not None and parsed == item["answer"])

        if parsed is None:
            n_parse_failed += 1
        if is_correct:
            n_correct += 1
        n_total += 1

        predictions.append({
            "question_id": item["question_id"],
            "prompt": prompt,
            "response": response,
            "parsed_answer": parsed,
            "correct_answer": item["answer"],
            "is_correct": is_correct,
            "strategy": args.strategy,
            "model": args.model,
        })

        if (i + 1) % 50 == 0:
            elapsed = time.time() - start_time
            acc = n_correct / n_total * 100 if n_total > 0 else 0
            print(f"[{i+1}/{len(items)}] acc={acc:.1f}% "
                  f"parse_fail={n_parse_failed} elapsed={elapsed:.1f}s",
                  file=sys.stderr)

    # Summary
    acc = n_correct / n_total * 100 if n_total > 0 else 0
    print(f"\n=== Summary ===", file=sys.stderr)
    print(f"Model:    {args.model}", file=sys.stderr)
    print(f"Strategy: {args.strategy}", file=sys.stderr)
    print(f"Tier:     {args.tier}", file=sys.stderr)
    print(f"Items:    {n_total}", file=sys.stderr)
    print(f"Correct:  {n_correct} ({acc:.2f}%)", file=sys.stderr)
    print(f"Parse fail: {n_parse_failed} ({n_parse_failed / n_total * 100:.1f}%)" if n_total else "",
          file=sys.stderr)

    # Write output
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with open(args.output, "w", encoding="utf-8") as f:
            for pred in predictions:
                f.write(json.dumps(pred, ensure_ascii=False) + "\n")
        print(f"\nWrote {len(predictions)} predictions to {args.output}", file=sys.stderr)
    else:
        for pred in predictions:
            print(json.dumps(pred, ensure_ascii=False))

    return 0


if __name__ == "__main__":
    sys.exit(main())
