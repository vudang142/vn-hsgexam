# VN-HSGExam Dataset Card

> **Format:** This dataset card follows the structure proposed by Gebru et al. (2021), "Datasheets for Datasets" (*Communications of the ACM*, 64(12), 86-92).
>
> **Version:** v1.0 (pre-release) — Last updated: 2026-01-15

---

## 1. Motivation

### For what purpose was the dataset created?

**VN-HSGExam** (Vietnamese High School Graduation Examination) was created to fill a critical gap in the evaluation of large language models (LLMs) on **low-to-medium-resource languages** and **curriculum-grounded knowledge** tasks. While benchmarks such as MMLU, GSM8K, and HumanEval dominate English LLM evaluation, dedicated benchmarks for **Vietnamese** educational tasks — particularly those aligned with the national curriculum — are scarce.

Specifically, VN-HSGExam enables research on:

1. **Multilingual LLM capability:** How well do open-weight LLMs (e.g., Qwen3 235B, Llama 3.1 8B, Vistral 7B) perform on culturally and linguistically specific Vietnamese content?
2. **Scale vs. specialization:** Does a Vietnamese-specialized model (Vistral 7B) outperform a comparably-sized universal model (Llama 3.1 8B)? Does scale dominate specialization?
3. **Prompting sensitivity:** How do zero-shot, few-shot, and chain-of-thought (CoT) prompting strategies interact with model scale on Vietnamese knowledge tasks?
4. **Subject-specific gaps:** Are there systematic gaps in LLM knowledge of Vietnamese civic, legal, geographic, historical, or biological content?
5. **Temporal contamination:** Are year-level accuracy patterns consistent with (or inconsistent with) data contamination from publicly available exam papers?

### Who created the dataset and on whose behalf?

The dataset was created by the **anonymous VN-HSGExam authors** (currently under double-blind review for ICDSAIA 2026). The corresponding author will be identified in the camera-ready version.

### Who funded the creation of the dataset?

This work was conducted as part of an independent research effort. No external funding source is declared at the time of pre-release. Compute was provided by **free-tier Cerebras and Groq APIs** for cloud inference, plus a single **Tesla T4 GPU** (Google Colab) for local inference of Vistral 7B.

---

## 2. Composition

### What do the instances that comprise the dataset represent?

Each instance is a **multiple-choice question (MCQ)** drawn from the official Vietnamese High School Graduation Examination (Kỳ thi tốt nghiệp THPT Quốc gia), administered by the Vietnamese Ministry of Education and Training (MoET). Each instance has:

- One **question stem** in Vietnamese.
- Four **answer choices** (A, B, C, D), exactly one of which is correct.
- A **correct answer key** (single letter) sourced from official MoET post-examination releases.
- **Metadata** including subject, year, position in the original exam, difficulty tier (easy/medium/hard), and an indicator of whether the item is included in the Tier 1 evaluation set or Tier 2 reserve.

### How many instances are there in total?

| Subset | Count | Description |
|--------|------:|-------------|
| **Raw** | 960 | All items from 4 subjects × 6 years × 40 items per exam |
| **Usable (text-only)** | 818 | Items not requiring visual references (atlas maps, diagrams, charts) |
| **Tier 1 (evaluation set)** | 516 | Balanced 129 items per subject, stratified by difficulty and year |
| **Tier 2 (reserve)** | 302 | Remaining usable items; also used as few-shot example pool |

### Does the dataset contain all possible instances or a sample?

The dataset is a **near-complete census** of text-evaluable items from the 2019–2024 MoET examinations across four subjects (History, Geography, Civics, Biology), subject to the visual-item exclusion protocol described in Section 4. Tier 1 is a **stratified random sample** (seed = 42) of the 818-item usable set, balanced at 129 items per subject.

### What data does each instance consist of?

Each instance is a JSON object with the following fields (see `docs/SCHEMA.md` for the formal schema):

- `id` (string): Unique identifier, e.g., `"HSG_2019_history_001"`.
- `subject` (string): One of `"history"`, `"geography"`, `"civics"`, `"biology"`.
- `year` (integer): Examination year, 2019–2024.
- `position` (integer): Question position in the original exam (1–40).
- `difficulty` (string): `"easy"`, `"medium"`, or `"hard"` (position-based proxy, see Section 4).
- `question` (string): The question stem in Vietnamese.
- `choices` (object): Map from choice letter (`"A"`, `"B"`, `"C"`, `"D"`) to the choice text in Vietnamese.
- `answer` (string): The correct choice letter.
- `requires_visual` (boolean): Whether the item was excluded from the usable set due to visual references.
- `tier` (integer, optional): `1` (evaluation set) or `2` (reserve) — present in tier-specific files only.

### Is there a label or target associated with each instance?

**Yes.** Each instance has a `answer` field containing the correct choice letter (`"A"`, `"B"`, `"C"`, or `"D"`), sourced from official MoET post-examination answer keys.

### Is any information missing from individual instances?

No. All 818 usable instances are complete with question text, all four choices, and answer keys. The 142 excluded items are not redistributed in this benchmark because they require visual references that cannot be rendered in plain text.

### Are there recommended data splits?

**Yes.** The benchmark ships with two pre-defined splits:

- **Tier 1 (`tier1_balanced.json`, 516 items):** Primary evaluation set. Stratified by subject (129 per subject), difficulty, and year. Sampling seed = 42 for full reproducibility.
- **Tier 2 (`tier2_extended.json`, 302 items):** Reserve set. Used for robustness checks and as the example pool for few-shot prompting (to guarantee zero overlap between in-context demonstrations and evaluation items).

### Are there errors, sources of noise, or redundancies in the dataset?

**Known limitations:**

1. **Position-based difficulty proxy** is a heuristic, not an empirically validated IRT estimate. Items 1–20 are labeled `easy`, 21–30 `medium`, 31–40 `hard`. This may not reflect true difficulty.
2. **Answer keys** are taken directly from official MoET releases; we did not perform a second-pass manual validation of all 818 items. Our "format validation" check confirmed structural correctness (correct number of choices, valid answer letter) but did not verify content accuracy.
3. **Possible item-level contamination** for exams from 2019–2022, which have been publicly available online for several years and may have appeared in LLM pretraining corpora. Our temporal contamination analysis (Section 6 of the paper) found no systematic signal, but cannot fully exclude incidental item-level exposure.

---

## 3. Collection Process

### How was the data associated with each instance acquired?

Data was acquired from **official MoET publications** of the annual Vietnamese High School Graduation Examination, covering the years 2019–2024. Specifically:

- **Source:** MoET website ([https://moet.gov.vn](https://moet.gov.vn)) and affiliated provincial education department portals.
- **Format:** Raw exam papers were obtained in plain text (`.txt`) format, manually transcribed from the official PDF releases.
- **Authorization:** The exam papers are released publicly by MoET after each examination cycle for transparency and public access. They contain no personal data, no student identifiers, and no proprietary content beyond the questions themselves.

### What mechanisms or procedures were used to collect the data?

The collection procedure consisted of the following steps:

1. **Acquisition** of raw exam papers (`.txt` format) from MoET official sources for the years 2019–2024.
2. **Parsing** using a custom Python parser (`src/parser/vn_hsgexam_parser.py`) that extracts the question stem, the four choices, and the answer key for each of the 40 questions in each exam.
3. **Visual-item tagging** — a tag-based protocol was applied to mark items that require visual references (atlas maps, diagrams, charts, phylogenetic trees, complex tables). Tagged items are excluded from the usable set.
4. **Answer-key validation** via automated format checks (correct number of choices, valid answer letter).
5. **Stratified sampling** to produce Tier 1 (516) and Tier 2 (302) using a fixed random seed (`42`).

### If the dataset is a sample from a larger set, what was the sampling strategy?

See Section 2: **stratified random sampling** by subject (target 129 per subject), difficulty (preserving each subject's natural distribution), and year (balanced across 2019–2024). Seed = 42.

### Who was involved in the data collection process?

The data was collected and processed by the **VN-HSGExam authors** (currently anonymous for double-blind review). No external annotators, crowdworkers, or third-party services were involved.

### Over what timeframe was the dataset collected?

The exam papers cover the years **2019–2024**. Collection and parsing were performed over a period of approximately **3 weeks** as part of the research project timeline.

### Were any ethical review processes completed?

The dataset is composed of **publicly available exam materials** released by a government ministry. The materials contain no personal data, no student responses, and no identifying information. The MoET releases the papers for public access as part of the official examination transparency process. No IRB review was required for use of these materials.

### Did you collect the data from the individuals in question directly, or obtain it via third parties or a data broker?

The data was obtained **directly from MoET official publications** (primary source), not via third-party aggregators or data brokers. The structured JSON representation in this repository is a derivative work created by the authors for research use, with full attribution to MoET as the source.

---

## 4. Preprocessing, Cleaning, and Labeling

### Was any preprocessing/cleaning/labeling of the data done?

**Yes.** The following processing was applied:

1. **Text normalization:** Trim whitespace, normalize Unicode (NFC), preserve Vietnamese diacritics.
2. **Visual-item tagging:** Items requiring visual references (atlas, diagrams, charts) were identified via a tag-based protocol and excluded from the usable set.
3. **Difficulty annotation:** Position-based labeling (items 1–20 = easy, 21–30 = medium, 31–40 = hard).
4. **Tier assignment:** Stratified random sampling with seed = 42.

### Was the "raw" data saved in addition to the preprocessed/cleaned/labeled data?

**Yes.** The full 960-item set is saved as `data/processed/vn_hsgexam_all.json`, and the 818-item usable set is saved as `data/processed/vn_hsgexam_usable.json`. Tier-specific files (`tier1_balanced.json`, `tier2_extended.json`) contain the stratified subsets.

### Is the software that was used to preprocess/clean/label the data available?

**Yes.** The parsing code is in `src/parser/vn_hsgexam_parser.py` and the sampling code is in `src/sampling/tier1_sampling.py`. These scripts can be re-run on the raw `.txt` files (not redistributed) to reproduce the full pipeline.

---

## 5. Uses

### Has the dataset been used for any tasks already?

**Yes.** The dataset is used in the accompanying paper for:

1. **MCQ accuracy evaluation** of 4 open-weight LLMs (Vistral 7B, Llama 3.1 8B, GPT-OSS 120B, Qwen3 235B) on Tier 1.
2. **Prompting strategy comparison** (zero-shot, few-shot, CoT, CoT-stochastic).
3. **Subject-level analysis** (Civics gap analysis).
4. **Temporal contamination analysis** (year-level accuracy patterns).
5. **Manual error analysis** on a 25-item subset of Civics errors (Qwen3 235B).

### What other tasks could the dataset be used for?

Potential downstream uses include:

- **Fine-tuning** Vietnamese LLMs on curricular knowledge (with appropriate licensing).
- **Retrieval-augmented generation (RAG)** evaluation.
- **Question-answering** benchmarks beyond MCQ.
- **Knowledge probing** of model internal representations.
- **Cross-lingual transfer** studies (e.g., comparing VN-HSGExam with KMMLU, CMMLU).
- **Educational AI** systems (e.g., tutoring, adaptive learning).

### Is there anything about the composition of the dataset or the way it was collected and preprocessed/cleaned/labeled that might impact future uses?

**Yes — important caveats:**

1. **Civics performance is artificially low** for all evaluated models due to the underrepresented Vietnamese legal content in pretraining corpora. This is a *finding*, not a *flaw*; researchers should report it as such.
2. **Geography is under-represented** in the usable set (129 of 240 raw items) due to the high rate of visual-item exclusion (46%).
3. **Position-based difficulty is a heuristic** and should not be used for high-stakes IRT-style analyses without empirical validation.
4. **The 2019–2022 exam papers have been publicly available online for several years** and may have been included in LLM pretraining corpora. Users should report year-level accuracy patterns alongside overall results.

### Is the dataset self-contained, or does it link to or otherwise rely on external resources?

**The dataset is self-contained** — all 818 items (and their tier assignments) are bundled in the JSON files. The dataset does *not* require any external resources to use. However, the **raw `.txt` exam files** are not redistributed (see Section 7); users wishing to reproduce the parsing pipeline should obtain the raw files from MoET directly.

### Does the dataset contain data that might be considered confidential?

**No.** The exam papers are public MoET releases containing no personal data, no student responses, and no proprietary content.

### Does the dataset contain data that, if viewed directly, might be offensive, insulting, threatening, or might otherwise cause anxiety?

**No.** The content is standard multiple-choice exam questions on academic subjects (History, Geography, Civics, Biology).

---

## 6. Distribution

### Will the dataset be distributed to third parties outside of the entity (e.g., company, institution, organization) on behalf of which the dataset was created?

**Yes.** The dataset is publicly released under **CC-BY-4.0** via:

1. **GitHub:** [https://github.com/vudang142/vn-hsgexam](https://github.com/vudang142/vn-hsgexam)
2. **Zenodo:** [https://doi.org/10.5281/zenodo.20687385](https://doi.org/10.5281/zenodo.20687385)

### How will the dataset will be distributed?

- **GitHub:** All JSON files, source code, documentation, and the Jupyter notebook are available in the public repository.
- **Zenodo:** Each tagged GitHub Release is automatically archived on Zenodo and assigned a persistent DOI. Users can cite the dataset using this DOI.

### When will the dataset be distributed?

The dataset was made **publicly available** on 2026-01-15 via Zenodo with DOI `10.5281/zenodo.20687385`, accompanying the ICDSAIA 2026 submission.

### Will the dataset be updated?

**Yes.** Future updates (e.g., adding Mathematics, Literature, English, Physics, Chemistry) are planned as future work. Each update will be versioned and released as a new Zenodo deposition with a new DOI.

### If the dataset is related to people, are there applicable limits on the retention of the data associated with the instances?

**Not applicable** — the dataset contains no personal data.

### If the dataset is related to people, were the individuals in question notified about the data collection and use?

**Not applicable.**

---

## 7. Maintenance

### Who will be supporting, hosting, and maintaining the dataset?

The **VN-HSGExam authors** (anonymous during review; full contact information to be provided in the camera-ready version) are responsible for maintenance. The dataset is hosted on:

- **GitHub** (primary, for issues and pull requests).
- **Zenodo** (long-term archival and DOI minting).

### How can the owner/curator of the dataset be contacted?

Please [open an issue](https://github.com/vudang142/vn-hsgexam/issues) on the GitHub repository. Contact email will be provided in the camera-ready paper.

### Is there an erratum?

Any errata will be tracked in [`CHANGELOG.md`](../CHANGELOG.md) and, if material, in a new Zenodo release with a corresponding citation note in the paper.

### Will the dataset be updated to correct errors and bugs?

**Yes.** Bugs and errors should be reported via GitHub issues. Material corrections will trigger a new minor version (e.g., v1.0 → v1.1) with a Zenodo release.

### If others want to extend/augment/build on/contribute to the dataset, can they do so?

**Yes — contributions are welcome.** Please open a GitHub issue to discuss proposed changes (e.g., adding new subjects, improving the visual-exclusion protocol) before submitting a pull request. All contributions must respect the CC-BY-4.0 license (attribution required).

---

## 8. Additional Information

### Has the dataset been used in any published research?

The accompanying paper is **under review at ICDSAIA 2026** (anonymous submission). The dataset has not yet appeared in any other publication.

### Are there any other comments?

- **Vietnamese version of this document** is not currently provided; an unofficial translation may be added in a future release if there is community interest.
- **Issues related to the dataset card itself** (e.g., missing fields, unclear wording) are welcome via GitHub issues.

---

## References

- Gebru, T., Morgenstern, J., Vecchione, B., Vaughan, J. W., Wallach, H., Daumé III, H., & Crawford, K. (2021). *Datasheets for datasets.* Communications of the ACM, 64(12), 86-92.
- Vietnamese Ministry of Education and Training (MoET). (2019–2024). *Kỳ thi tốt nghiệp Trung học Phổ thông Quốc gia* [National High School Graduation Examination papers]. Retrieved from [https://moet.gov.vn](https://moet.gov.vn).
