# VN-HSGExam: A Vietnamese High School Graduation Examination Benchmark for LLM Evaluation

[![License: CC BY 4.0](https://img.shields.io/badge/Data_License-CC_BY_4.0-lightgrey.svg)](https://creativecommons.org/licenses/by/4.0/)
[![License: MIT](https://img.shields.io/badge/Code_License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.20687385.svg)](https://doi.org/10.5281/zenodo.20687385)
[![Status](https://img.shields.io/badge/Status-Pre--release-orange.svg)](#citation)

> **Benchmark for evaluating Large Language Models on Vietnamese High School Graduation Examinations (Kỳ thi tốt nghiệp THPT Quốc gia, 2019–2024).**

This repository accompanies the paper:

> **"Evaluating Open-Weight Language Models on Vietnamese High School Knowledge: Effects of Scale, Specialization, and Prompting"** — under review at **ICDSAIA 2026**.

---

## 📌 Overview

VN-HSGExam is a multiple-choice question (MCQ) benchmark drawn from the official Vietnamese High School Graduation Examination, administered annually by the **Ministry of Education and Training (MoET)**. The dataset spans **4 subjects × 6 years (2019–2024)**:

- **History** (Lịch sử) — 240 raw → 240 text-evaluable items
- **Geography** (Địa lý) — 240 raw → 129 text-evaluable items (46% require visual atlas)
- **Civics** (Giáo dục Công dân / GDCD) — 240 raw → 240 text-evaluable items
- **Biology** (Sinh học) — 240 raw → 209 text-evaluable items

After filtering items that require visual reasoning (atlas maps, diagrams, charts, phylogenetic trees), the benchmark contains **818 text-evaluable MCQs**, organized into a balanced 516-item Tier 1 evaluation subset and a 302-item Tier 2 reserve.

| Subject | Total Items | Usable (text-only) | Excluded |
|---------|------------:|-------------------:|---------:|
| History  | 240 | 240 | 0   |
| Geography| 240 | 129 | 111 |
| Civics   | 240 | 240 | 0   |
| Biology  | 240 | 209 | 31  |
| **Total**| **960** | **818** | **142** |

### Two-tier evaluation strategy

- **Tier 1** (`data/processed/tier1_balanced.json`) — **516 questions**, balanced at 129 per subject, used for all primary experiments. Stratified sampling by difficulty (easy/medium/hard) and year, fixed random seed `42`.
- **Tier 2** (`data/processed/tier2_extended.json`) — **302 remaining usable questions**, used for robustness checks and few-shot example pools.

---

## 🗂️ Repository Structure

```
vn-hsgexam/
├── data/
│   └── processed/                        # Parsed JSON datasets + sampling outputs
│       ├── vn_hsgexam_all.json           # All 960 raw items
│       ├── vn_hsgexam_usable.json        # 818 text-evaluable items
│       ├── tier1_balanced.json           # 516-item evaluation set
│       ├── tier2_extended.json           # 302-item reserve
│       ├── tier1_gptoss.jsonl            # GPT-OSS 120B raw responses (Tier 1)
│       ├── *_report.{md,json}            # Parsing & sampling reports
├── src/
│   ├── parser/                           # Raw .txt -> structured JSON
│   │   ├── vn_hsgexam_parser.py
│   │   └── batch_parse.py
│   ├── sampling/                         # Tier 1 / Tier 2 stratified sampling
│   │   └── tier1_sampling.py
│   └── inference/                        # LLM client (Cerebras / Groq / llama.cpp)
│       └── llm_client.py
├── notebooks/
│   └── vn_hsgexam_colab.ipynb            # End-to-end Colab pipeline
├── examples/
│   └── load_and_evaluate.py              # Minimal evaluation example
├── results/                              # CSV results and figures (paper-ready)
│   ├── overall_accuracy_pivot.csv
│   ├── subject_analysis_by_strategy.csv
│   ├── difficulty_analysis_best_strategy.csv
│   ├── mcnemar_tests.csv
│   ├── error_analysis_sample.csv
│   ├── latex_tables.txt
│   └── *.png
├── docs/
│   ├── DATASETS.md                       # Dataset card (Gebru et al. 2021)
│   └── SCHEMA.md                         # JSON schema documentation
├── .gitignore
├── LICENSE                               # CC-BY-4.0 (data) + MIT (code)
├── LICENSE-CODE                          # MIT for source code
├── LICENSE-DATA                          # CC-BY-4.0 for dataset
├── CITATION.cff                          # GitHub-Zenodo citation metadata
├── CHANGELOG.md                          # Version history
└── README.md                             # This file
```

> **Note:** Raw `.txt` exam files are **not** redistributed in this repository (see [Acknowledgements](#acknowledgements) and `docs/DATASETS.md`).

---

## 🚀 Quick Start

### Installation

```bash
git clone https://github.com/vudang142/vn-hsgexam.git
cd vn-hsgexam
pip install -r requirements.txt   # (see requirements.txt for dependencies)
```

### Loading the dataset

```python
import json
from pathlib import Path

DATA_DIR = Path("data/processed")

with open(DATA_DIR / "tier1_balanced.json", encoding="utf-8") as f:
    tier1 = json.load(f)

print(f"Tier 1 size: {len(tier1)} questions")
print(f"First item: {tier1[0]['id']} ({tier1[0]['subject']}, {tier1[0]['year']})")
# Example output:
#   First item: HSG_2019_history_001 (history, 2019)
```

### Evaluating a model (minimal example)

See [`examples/load_and_evaluate.py`](examples/load_and_evaluate.py) for a complete reproducible evaluation script that:

1. Loads Tier 1 items.
2. Applies one of four prompting strategies (zero-shot, few-shot, CoT, CoT-stochastic).
3. Calls a model API (Cerebras / Groq) or a local llama.cpp instance.
4. Parses the predicted letter and writes predictions to a JSONL file.

```bash
python examples/load_and_evaluate.py \
    --model qwen3-235b \
    --strategy few_shot \
    --tier 1 \
    --output results/predictions_qwen3_fewshot.jsonl
```

---

## 📊 Headline Results (from the paper)

Evaluated 4 open-weight LLMs × 4 prompting strategies on the 516-item Tier 1 set (**8,256 total inference calls**):

| Model | Params | Zero-shot | Few-shot | CoT | CoT-stoch | Best |
|-------|-------:|----------:|---------:|----:|----------:|-----:|
| Vistral 7B (Q4)        | 7B   | 46.1 | 52.5 | 48.1 | 44.8 | 52.5 |
| Llama 3.1 8B           | 8B   | 50.4 | 54.5 | 53.7 | 53.3 | 54.5 |
| GPT-OSS 120B (5.1B act)| 120B | 60.9 | 61.2 | 59.3 | 59.7 | 61.2 |
| Qwen3 235B (22B act)   | 235B | 68.0 | 67.1 | 68.2 | 68.4 | 68.4 |

**Key findings** (full statistical analysis in the paper):

1. **Scale dominates specialization:** Qwen3 235B exceeds the Vietnamese-specialized Vistral 7B by **+15.9 percentage points**.
2. **Civics is uniformly the hardest subject** across all models (peak 38–44%), with a **25–40 pp gap** to other subjects, driven primarily by Vietnamese legal-concept knowledge deficits (64% of errors) rather than reasoning failures (12%).
3. **Prompting sensitivity is statistically significant only for sub-10B models** (McNemar p = 0.0002 for Vistral 7B; p > 0.24 for Qwen3 235B).

See `results/` for the full set of CSVs and figures used in the paper.

---

## 📖 Dataset Documentation

- **[`docs/DATASETS.md`](docs/DATASETS.md)** — Full dataset card (Gebru et al. 2021 format): motivation, composition, collection process, preprocessing, intended uses, ethical considerations, distribution, maintenance.
- **[`docs/SCHEMA.md`](docs/SCHEMA.md)** — Field-by-field description of the JSON structure for `tier1_balanced.json` and `tier2_extended.json`.

---

## 📋 Reproducing the Dataset

If you have the raw MoET `.txt` files locally (not redistributed):

```bash
# 1. Parse raw .txt files into structured JSON
python src/parser/batch_parse.py \
    --input-dir raw/ \
    --output-dir data/processed/

# 2. Sample Tier 1 (516) and Tier 2 (302) subsets
python src/sampling/tier1_sampling.py \
    --input data/processed/vn_hsgexam_usable.json \
    --output-dir data/processed/
```

**Random seed:** `42` (fixed; recorded in `data/processed/tier1_report.md`).

---

## 🧪 Difficulty Heuristic

Difficulty labels follow the MoET question-ordering convention used in Vietnamese national examinations:

- **Easy:** items 1–20 (first 50% of each subject's 40 questions)
- **Medium:** items 21–30 (next 25%)
- **Hard:** items 31–40 (last 25%)

⚠️ **Caveat:** This is a *position-based proxy*, not an empirically validated Item Response Theory (IRT) estimate. We acknowledge this as a limitation in the paper and flag IRT validation as future work.

---

## 📜 License

This repository is dual-licensed:

- **Dataset (all JSON files in `data/processed/`):** [CC-BY-4.0](https://creativecommons.org/licenses/by/4.0/) — see [`LICENSE-DATA`](LICENSE-DATA).
- **Source code (in `src/`, `notebooks/`, `examples/`):** [MIT](https://opensource.org/licenses/MIT) — see [`LICENSE-CODE`](LICENSE-CODE).

The exam content is sourced from official MoET publications and is in the public domain for non-commercial academic use. This repository redistributes items in structured (parsed) form with full attribution.

---

## 🙏 Acknowledgements

The exam materials are official **Vietnamese Ministry of Education and Training (MoET)** publications, released publicly after each examination cycle. This repository redistributes them in structured form **solely for non-commercial academic research use**. Raw exam materials are not included; please obtain them from the [MoET portal](https://moet.gov.vn) directly.

We thank the open-source Vietnamese NLP community — Vistral, PhoGPT, VinaLLaMA, and the VMLU/VLSP benchmark teams — for foundational work that informed this study.

---

## 📬 Contact

For questions, bug reports, or collaboration inquiries, please [open an issue](https://github.com/vudang142/vn-hsgexam/issues) on this repository.

---

## 📑 Citation

If you use VN-HSGExam in your research, please cite both the paper and the dataset (Zenodo DOI will be assigned upon first release).

### BibTeX — Paper (under review)

```bibtex
@inproceedings{anonymous2026vnhsgexam,
  title     = {Evaluating Open-Weight Language Models on Vietnamese High
               School Knowledge: Effects of Scale, Specialization, and
               Prompting},
  author    = {Anonymous},
  booktitle = {Proceedings of the International Conference on Data Science
               and Artificial Intelligence (ICDSAIA 2026)},
  year      = {2026},
  note      = {Under review}
}
```

### BibTeX — Dataset (Zenodo)

```bibtex
@dataset{anonymous2026vnhsgexam_dataset,
  author    = {Anonymous},
  title     = {{VN-HSGExam}: A Vietnamese High School Graduation
               Examination Benchmark for {LLM} Evaluation (v1.0)},
  year      = {2026},
  publisher = {Zenodo},
  doi       = {10.5281/zenodo.20687385},
  url       = {https://doi.org/10.5281/zenodo.20687385}
}
```

> **Note:** See [`CITATION.cff`](CITATION.cff) for the machine-readable version.

---

## 📝 Changelog

See [`CHANGELOG.md`](CHANGELOG.md) for the version history.

- **v1.0** (TBD) — Initial public release accompanying the ICDSAIA 2026 submission.

---

*Repository status: 🟡 Pre-release. Will be made public upon paper acceptance.*
