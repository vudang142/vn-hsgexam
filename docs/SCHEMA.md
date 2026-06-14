# VN-HSGExam JSON Schema Documentation

> **Version:** v1.0 · **Last updated:** 2026-01-15
>
> This document describes the structure of the JSON files in `data/processed/`. For a machine-readable specification, see [`schema/tier_item.schema.json`](schema/tier_item.schema.json) (JSON Schema Draft-07).

---

## 1. File Inventory

| File | Format | Item count | Description |
|------|--------|-----------:|-------------|
| `vn_hsgexam_all.json`         | JSON array | 960 | All raw items from 4 subjects × 6 years |
| `vn_hsgexam_usable.json`      | JSON array | 818 | Text-evaluable items only (excludes visual items) |
| `tier1_balanced.json`         | JSON array | 516 | Tier 1 evaluation set (balanced, stratified) |
| `tier2_extended.json`         | JSON array | 302 | Tier 2 reserve (used for few-shot examples & robustness) |
| `tier1_gptoss.jsonl`          | JSON Lines | 516 | GPT-OSS 120B raw responses on Tier 1 (one JSON per line) |
| `*_report.{md,json}`          | Reports    | —   | Parsing & sampling statistics |

> **Note:** All JSON files use **UTF-8** encoding and preserve Vietnamese diacritics. All JSON files are top-level arrays of items (not wrapped in an object).

---

## 2. Item Schema (Tier 1 & Tier 2)

Each item in `tier1_balanced.json` and `tier2_extended.json` is a JSON object with the following fields:

### 2.1 Top-level fields

| Field | Type | Required | Description |
|-------|------|:--------:|-------------|
| `question_id`     | `string`  | ✅ | Unique identifier across the dataset. Format: `"{subject}_{year}_q{number}"`, e.g., `"biology_2019_q100"`, `"civics_2024_q85"`. |
| `subject`         | `string`  | ✅ | One of `"history"`, `"geography"`, `"civics"`, `"biology"`. |
| `year`            | `integer` | ✅ | Examination year. Integer in `[2019, 2024]`. |
| `question_number` | `integer` | ✅ | Question position in the original exam paper. Integer in `[1, 40]`. |
| `stem`            | `string`  | ✅ | Question stem in Vietnamese. UTF-8 encoded, diacritics preserved. |
| `choices`         | `object`  | ✅ | Map of choice letter to choice text. Always has exactly 4 keys: `"A"`, `"B"`, `"C"`, `"D"`. |
| `answer`          | `string`  | ✅ | Correct answer letter. One of `"A"`, `"B"`, `"C"`, `"D"`. Sourced from official MoET answer keys. |
| `is_usable`       | `boolean` | ✅ | Always `true` for items in Tier 1 / Tier 2 (these files contain only usable items). |
| `exclusion_tag`   | `string \| null` | ✅ | Reason for exclusion from the usable set, or `null` if the item is usable. Always `null` in Tier 1 / Tier 2. Possible non-null values in `vn_hsgexam_all.json`: `"atlas"`, `"diagram"`, `"chart"`, `"table_complex"`, `"phylogenetic_tree"`, etc. |
| `difficulty`      | `string`  | ✅ | Position-based difficulty proxy. One of `"easy"` (q1–20), `"medium"` (q21–30), `"hard"` (q31–40). |
| `metadata`        | `object`  | ✅ | Auxiliary statistics about the question stem. See §2.3. |

### 2.2 `choices` object

```json
{
  "A": "Thể một.",
  "B": "Thể ba.",
  "C": "Thể tam bội.",
  "D": "Thể tứ bội."
}
```

- **Keys:** exactly `"A"`, `"B"`, `"C"`, `"D"` (uppercase, no extras).
- **Values:** non-empty Vietnamese strings, each corresponding to one answer choice.
- **Order:** keys are sorted lexicographically in the JSON output, but their original order in the exam is preserved by the value content (not by key order).

### 2.3 `metadata` object

| Field | Type | Description |
|-------|------|-------------|
| `stem_char_length` | `integer` | Number of Unicode characters in `stem` (excluding whitespace). |
| `stem_line_count`  | `integer` | Number of lines in `stem` (1 for most items). |

> This object may be extended in future versions. New fields are added additively and do not break existing consumers.

### 2.4 Example item (from Tier 1)

```json
{
  "question_id": "biology_2019_q100",
  "subject": "biology",
  "year": 2019,
  "question_number": 100,
  "stem": "Một loài thực vật có bộ NST 2n. Hợp tử có bộ NST 2n + 1 có thể phát triển thành thể đột biến nào sau đây?",
  "choices": {
    "A": "Thể một.",
    "B": "Thể ba.",
    "C": "Thể tam bội.",
    "D": "Thể tứ bội."
  },
  "answer": "B",
  "is_usable": true,
  "exclusion_tag": null,
  "difficulty": "easy",
  "metadata": {
    "stem_char_length": 105,
    "stem_line_count": 1
  }
}
```

---

## 3. Items in `vn_hsgexam_all.json` (raw, including excluded)

Identical to the schema above, but:

- `is_usable` is `true` for 818 items, `false` for 142 items.
- `exclusion_tag` is `null` for usable items, and a non-null string (e.g., `"atlas"`, `"diagram"`) for excluded items.

The 142 excluded items require visual references (atlas maps, diagrams, charts, phylogenetic trees, complex tables) and cannot be answered correctly from text alone.

---

## 4. JSON Lines File: `tier1_gptoss.jsonl`

This file contains the **raw responses** from GPT-OSS 120B for the 516 Tier 1 items under one of the four prompting strategies. Each line is a JSON object with the following schema:

| Field | Type | Description |
|-------|------|-------------|
| `question_id` | `string` | Matches `question_id` in `tier1_balanced.json`. |
| `prompt` | `string` | The full prompt sent to the model. |
| `response` | `string` | The raw model response (may include reasoning + final answer). |
| `parsed_answer` | `string \| null` | The model's predicted choice letter, extracted from the response. `null` if parsing failed. |
| `is_correct` | `boolean` | `true` if `parsed_answer == correct_answer`. |
| `strategy` | `string` | The prompting strategy used: `"zero_shot"`, `"few_shot"`, `"cot"`, or `"cot_stochastic"`. |
| `latency_ms` | `integer` | API call latency in milliseconds. |
| `timestamp` | `string` | ISO 8601 timestamp of the API call. |

Other models' prediction files follow the same schema and are released under `results/predictions/` in the full evaluation harness (not included in v1.0 pre-release).

---

## 5. Validation

You can validate any Tier 1 / Tier 2 JSON file against the formal schema using a JSON Schema validator. For example, with Python:

```bash
pip install jsonschema
python -c "
import json, jsonschema
with open('data/processed/tier1_balanced.json', encoding='utf-8') as f:
    data = json.load(f)
with open('docs/schema/tier_item.schema.json', encoding='utf-8') as f:
    schema = json.load(f)
for i, item in enumerate(data):
    try:
        jsonschema.validate(item, schema)
    except jsonschema.ValidationError as e:
        print(f'Item {i} ({item.get(\"question_id\")}) is invalid: {e}')
        break
else:
    print(f'All {len(data)} items valid.')
"
```

---

## 6. Versioning

The schema follows **semantic versioning** (`MAJOR.MINOR.PATCH`):

- **MAJOR:** Breaking changes (e.g., removing a required field, renaming a field).
- **MINOR:** Backward-compatible additions (e.g., new optional fields in `metadata`).
- **PATCH:** Documentation or schema-description fixes only.

The current schema is **v1.0.0**. Any v1.x release is guaranteed to be backward-compatible with consumers written against v1.0.0.

---

## 7. Schema File

The machine-readable schema is in [`schema/tier_item.schema.json`](schema/tier_item.schema.json) (JSON Schema Draft-07). Use it for automated validation in CI pipelines.
