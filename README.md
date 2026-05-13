# VN-HSGExam

Benchmark for evaluating Large Language Models on Vietnamese High School Graduation Examinations.

> **Status**: 🚧 Work in progress (Week 3 of 6). Repository is private during paper preparation. Will be made public upon submission to ICDSAIA 2026.

## Overview

VN-HSGExam is a multiple-choice question benchmark drawn from the official Vietnamese High School Graduation Examination (Kỳ thi tốt nghiệp THPT Quốc gia), administered annually by the Ministry of Education and Training (MoET). The dataset spans **4 subjects × 6 years (2019–2024)**:

- **History** (Lịch sử) — questions 1–40
- **Geography** (Địa lý) — questions 41–80
- **Civics** (Giáo dục Công dân) — questions 81–120
- **Biology** (Sinh học) — questions 81–120

This work accompanies the paper *"Benchmarking Large Language Models on Vietnamese High School Graduation Examinations: A Comparative Study of Prompting Strategies"* (under submission to ICDSAIA 2026).

## Dataset

After parsing 24 exam papers (4 subjects × 6 years), the dataset contains 960 multiple-choice questions. Questions requiring visual reasoning (Atlas maps, diagrams, charts, pedigrees, complex tables) are excluded from the evaluation set.

| Subject | Total Items | Usable (text-only) | Excluded |
|---|---:|---:|---:|
| History | 240 | 240 | 0 |
| Geography | 240 | 129 | 111 |
| Civics | 240 | 240 | 0 |
| Biology | 240 | 209 | 31 |
| **Total** | **960** | **818** | **142** |

### Two-tier evaluation strategy

- **Tier 1 (`tier1_balanced.json`)** — 516 questions, balanced at 129 per subject. Used for all primary experiments. Within each subject, sampling is stratified by difficulty (preserving the subject's natural distribution) and balanced across years.
- **Tier 2 (`tier2_extended.json`)** — 302 remaining usable questions, used for robustness checks.

Sampling uses a fixed random seed (`SAMPLING_SEED=42`) for full reproducibility.

### Tier 1 composition

| Subject | Easy | Medium | Hard | Total |
|---|---:|---:|---:|---:|
| History | 65 | 32 | 32 | 129 |
| Geography | 30 | 51 | 48 | 129 |
| Civics | 65 | 32 | 32 | 129 |
| Biology | 73 | 35 | 21 | 129 |

## Repository Structure

```
vn-hsgexam/
├── data/
│   └── processed/                # parsed JSON datasets + sampling outputs
│       ├── vn_hsgexam_all.json
│       ├── vn_hsgexam_usable.json
│       ├── tier1_balanced.json
│       ├── tier2_extended.json
│       └── *_report.{md,json}
├── src/
│   ├── parser/                   # raw .txt -> structured JSON
│   │   ├── vn_hsgexam_parser.py
│   │   └── batch_parse.py
│   └── sampling/                 # Tier 1 / Tier 2 stratified sampling
│       └── tier1_sampling.py
└── notebooks/
    └── vn_hsgexam_colab.ipynb    # end-to-end pipeline (Colab-ready)
```

Raw `.txt` exam files are not redistributed in this repository (see Acknowledgements).

## Reproducing the dataset

```bash
# 1. Parse raw .txt files (requires raw/ directory with 48 .txt files)
python src/parser/batch_parse.py --input-dir raw --output-dir data/processed

# 2. Sample Tier 1 and Tier 2
python src/sampling/tier1_sampling.py \
    --input data/processed/vn_hsgexam_usable.json \
    --output-dir data/processed
```

## Difficulty heuristic

Difficulty labels follow the official Vietnamese MoET question-ordering convention: the first 50% of questions in each subject are labeled `easy`, the next 25% `medium`, and the last 25% `hard`. This heuristic will be validated against model accuracy in the analysis section of the paper.

## Citation

Coming soon (paper under review).

## License

TBD — will be added before public release.

## Acknowledgements

The exam materials are official Vietnamese Ministry of Education and Training (MoET) publications. This repository redistributes them in structured (parsed) form solely for non-commercial academic research use. Raw exam materials are not included.
