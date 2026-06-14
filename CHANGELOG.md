# Changelog

All notable changes to **VN-HSGExam** will be documented in this file. The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html) for dataset releases.

---

## [Unreleased]

### Planned for v1.1
- Add Mathematics, Literature, English, Physics, Chemistry subjects.
- Add essay-format university entrance examination items.
- Validate position-based difficulty proxy against empirical Item Response Theory (IRT).
- Add closed-weight model baselines (GPT-4o, Claude, Gemini).
- Multi-sample self-consistency evaluation (≥5 samples per item).

---

## [1.0.0] - TBD (Public release)

### Added
- **Dataset:**
  - 818 text-evaluable multiple-choice questions from official Vietnamese MoET High School Graduation Examinations (2019–2024) across 4 subjects: History, Geography, Civics, Biology.
  - Tier 1 evaluation set: 516 questions (129 per subject, stratified by difficulty and year, fixed random seed = 42).
  - Tier 2 reserve: 302 remaining questions.
  - `vn_hsgexam_all.json` (960 raw items, including 142 visual-item exclusions).
  - `vn_hsgexam_usable.json` (818 text-evaluable items).
  - JSON Schema for automated validation (`docs/schema/tier_item.schema.json`).
- **Documentation:**
  - `README.md` (project landing page with quick start, headline results, citation).
  - `docs/DATASETS.md` (full dataset card following Gebru et al. 2021).
  - `docs/SCHEMA.md` (field-by-field schema documentation).
  - `docs/schema/tier_item.schema.json` (machine-readable JSON Schema).
  - `CITATION.cff` (GitHub-Zenodo citation metadata).
  - `LICENSE`, `LICENSE-DATA` (CC-BY-4.0), `LICENSE-CODE` (MIT).
  - `CHANGELOG.md` (this file).
- **Source code:**
  - `src/parser/vn_hsgexam_parser.py` — raw `.txt` → structured JSON parser.
  - `src/parser/batch_parse.py` — batch parsing of 24 exam papers.
  - `src/sampling/tier1_sampling.py` — stratified Tier 1 / Tier 2 sampling.
  - `src/inference/llm_client.py` — LLM client (Cerebras / Groq / llama.cpp).
  - `notebooks/vn_hsgexam_colab.ipynb` — end-to-end Colab pipeline.
  - `examples/load_and_evaluate.py` — minimal evaluation example.
- **Results:**
  - `analysis/overall_accuracy_pivot.csv` — accuracy by model × strategy.
  - `analysis/subject_analysis_by_strategy.csv` — accuracy by model × strategy × subject.
  - `analysis/best_subject_accuracy.csv` — best per-subject accuracy.
  - `analysis/difficulty_analysis_*.csv` — accuracy by difficulty tier.
  - `analysis/mcnemar_tests.csv` — McNemar's test p-values.
  - `analysis/error_analysis_sample.csv` — 25-item manual error taxonomy.
  - `analysis/latex_tables.txt` — LaTeX-formatted tables for the paper.
  - `analysis/fig_*.png` — publication-ready figures.

### Citation
If you use VN-HSGExam v1.0.0 in your research, please cite:

```bibtex
@dataset{anonymous2026vnhsgexam_v1,
  author    = {Anonymous},
  title     = {{VN-HSGExam}: A Vietnamese High School Graduation
               Examination Benchmark for {LLM} Evaluation (v1.0.0)},
  year      = {2026},
  publisher = {Zenodo},
  doi       = {10.5281/zenodo.20687385},
  url       = {https://doi.org/10.5281/zenodo.20687385}
}
```

---

## Versioning

- **MAJOR** (e.g., 1.0.0 → 2.0.0): breaking schema changes, removal of required fields, substantial restructuring of the dataset.
- **MINOR** (e.g., 1.0.0 → 1.1.0): backward-compatible additions (new subjects, new optional fields).
- **PATCH** (e.g., 1.0.0 → 1.0.1): documentation or schema-description fixes, no data changes.

Each version receives a separate Zenodo deposition and DOI.
