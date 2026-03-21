# HP-NER: Full Project Plan

## Repository Layout

```
hp-ner/
├── pyproject.toml             # UV-managed dependencies
├── README.md
├── .python-version
├── data/
│   ├── raw/                   # Scraped HTML/text
│   ├── filtered/              # Post-filtering sentences
│   ├── annotated/             # IOB2 annotation files per annotator
│   ├── merged/                # Adjudicated gold standard
│   └── ewt/                   # EWT train/dev/test (IOB2)
├── src/
│   └── hp_ner/
│       ├── __init__.py
│       ├── scraping/
│       │   ├── __init__.py
│       │   ├── scraper.py         # WikiScraper class
│       │   └── cleaner.py         # TextCleaner class
│       ├── preprocessing/
│       │   ├── __init__.py
│       │   ├── sentence_filter.py # SentenceFilter class
│       │   └── iob2.py            # IOB2Reader / IOB2Writer classes
│       ├── annotation/
│       │   ├── __init__.py
│       │   └── agreement.py       # AgreementCalculator (Cohen's kappa)
│       ├── models/
│       │   ├── __init__.py
│       │   ├── baseline.py        # BertNERBaseline class
│       │   ├── enhanced.py        # EnhancedNER class (DAPT + CRF)
│       │   └── llm_eval.py        # LLMEvaluator class (OpenAI/Anthropic API)
│       ├── training/
│       │   ├── __init__.py
│       │   ├── trainer.py         # NERTrainer class
│       │   └── dapt.py            # DomainAdaptivePretrainer class
│       └── evaluation/
│           ├── __init__.py
│           ├── metrics.py         # MetricsCalculator class
│           ├── ablation.py        # AblationStudy class
│           ├── learning_curve.py  # LearningCurveAnalyzer class
│           └── analysis.py        # QualitativeAnalyzer class
├── scripts/
│   ├── run_scrape.py
│   ├── run_filter.py
│   ├── run_agreement.py
│   ├── run_train_baseline.py
│   ├── run_train_enhanced.py
│   ├── run_eval_llm.py
│   └── run_analysis.py
└── notebooks/                 # Exploratory / result visualization only
```

---

## Phase 1 — Data Collection

**`scraping/scraper.py` → `WikiScraper`**
- Input: seed URLs (Harry Potter Fandom wiki categories)
- Uses `requests` + `BeautifulSoup4`; respects `robots.txt`
- Recursively follows internal links up to configurable depth
- Outputs: raw `.jsonl` with `{url, title, paragraphs[]}`

**`scraping/cleaner.py` → `TextCleaner`**
- Strips wiki markup artifacts, citation brackets `[1]`, infobox text
- Unicode normalization (NFC)

**`preprocessing/sentence_filter.py` → `SentenceFilter`**

Filtering criteria to implement:
- Min tokens: 5, Max tokens: 60 (configurable)
- Drop sentences with >40% numeric tokens
- Drop sentences with unbalanced parentheses
- Drop if detected language ≠ English (via `langdetect`)
- MinHash deduplication (Jaccard threshold 0.8) via `datasketch`

---

## Phase 2 — Annotation

**Format:** IOB2, one token per line, space-separated: `token label`

**Entity types:**
| Tag | Description |
|---|---|
| `CHARACTER` | Named persons (Harry Potter, Dumbledore) |
| `LOCATION` | Places (Hogwarts, Diagon Alley) |
| `ORGANIZATION` | Groups/institutions (Ministry of Magic, Order of the Phoenix) |
| `CREATURE` | Non-human beings (Dementor, Hippogriff) |
| `SPELL` | Incantations (Expelliarmus, Avada Kedavra) |
| `ARTIFACT` | Objects with narrative significance (Horcrux, Marauder's Map) |

**Overlap strategy:**
- Assign 85% of sentences uniquely per annotator
- 15% shared across all annotators → IAA calculation

**`annotation/agreement.py` → `AgreementCalculator`**
- Converts IOB2 spans to (start, end, label) tuples
- Computes token-level and span-level Cohen's κ
- Reports per-class κ breakdown
- Target: κ ≥ 0.7 before merging

---

## Phase 3 — Baseline Model

**`models/baseline.py` → `BertNERBaseline`**

```
Recommended model: dslim/bert-base-NER
Alternatives (stronger):
  - dbmdz/bert-large-cased-finetuned-conll03-english
  - Jean-Baptiste/roberta-large-ner-english
  - microsoft/deberta-v3-base  ← recommended upgrade
  - studio-ousia/luke-base     ← entity-aware, best for NER
```

- Load via `transformers.AutoModelForTokenClassification`
- Replace classification head to match HP label set
- Fine-tune on annotated HP train split + EWT train split
- Evaluate on HP dev / EWT dev
- Save best checkpoint by span-F1

**`training/trainer.py` → `NERTrainer`**
- Wraps HuggingFace `Trainer` with custom `DataCollatorForTokenClassification`
- Handles subword-to-word label alignment
- Early stopping on dev span-F1 (patience=3)

---

## Phase 4 — Enhanced Model

### Enhancement A: Domain-Adaptive Pretraining (DAPT)

**`training/dapt.py` → `DomainAdaptivePretrainer`**
- Continue MLM on scraped HP corpus (before fine-tuning)
- Uses `DataCollatorForLanguageModeling` (mlm_probability=0.15)
- Run for ~3 epochs on HP corpus
- Save adapted checkpoint → used as init for fine-tuning

### Enhancement B: CRF Decoding Layer

**`models/enhanced.py` → `EnhancedNER`**
- Replaces softmax head with linear-chain CRF (`torchcrf`)
- Encodes valid IOB2 transitions as hard constraints in transition matrix
- Otherwise same training loop as baseline

**Stack both:** DAPT init → fine-tune with CRF head = full enhanced model.

---

## Phase 5 — LLM Evaluation

**`models/llm_eval.py` → `LLMEvaluator`**
- Zero-shot prompt per sentence to GPT-4o or Claude via API
- System prompt defines all 6 entity types with examples
- Parses JSON response `{entities: [{text, label, start, end}]}`
- Converts to IOB2 for unified evaluation
- Rate-limited with exponential backoff

Prompt template:
```
You are a Named Entity Recognition system for the Harry Potter universe.
Identify all named entities in the sentence below.
Entity types: CHARACTER, LOCATION, ORGANIZATION, CREATURE, SPELL, ARTIFACT.
Return ONLY valid JSON: {"entities": [{"text": "...", "label": "...", "start": N, "end": N}]}

Sentence: {sentence}
```

---

## Phase 6 — Evaluation & Analysis

### Metrics (`evaluation/metrics.py` → `MetricsCalculator`)

| Metric | Implementation |
|---|---|
| Span-level P/R/F1 | `seqeval` library |
| Per-class F1 | `seqeval` with `scheme=IOB2` |
| Partial match (boundary correct, label wrong) | Custom: compare span boundaries independently of label |
| Exact span accuracy | Custom: strict (start, end, label) match |
| Majority-class baseline | Always predict most frequent entity token |

### Ablation Study (`evaluation/ablation.py` → `AblationStudy`)

Run in order, each as separate experiment:
1. BERT (no fine-tuning) → majority class F1
2. BERT fine-tuned on EWT only
3. BERT fine-tuned on HP annotated only
4. BERT fine-tuned on EWT + HP
5. DAPT → fine-tune on EWT + HP
6. DAPT → fine-tune with CRF on EWT + HP (= full enhanced)
7. LLM zero-shot
8. LLM few-shot (5 examples in prompt)

### Learning Curve (`evaluation/learning_curve.py` → `LearningCurveAnalyzer`)
- Train on [10%, 20%, 40%, 60%, 80%, 100%] of HP annotated train
- Plot dev F1 vs. train size for baseline and enhanced model

### Qualitative Analysis (`evaluation/analysis.py` → `QualitativeAnalyzer`)
- Confusion matrix across entity types
- Error bucketing: missed entities / wrong label / boundary off / spurious
- Per-sentence difficulty scoring (entity density, sentence length)

### Feature / Input Importance
- Integrated Gradients via `captum` library on baseline model
- Token attribution for FP and FN examples
- Report top-10 tokens per entity type that drive predictions

---

## pyproject.toml (UV)

```toml
[project]
name = "hp-ner"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
  "transformers>=4.40",
  "datasets>=2.19",
  "torch>=2.2",
  "torchcrf>=1.1",
  "seqeval>=1.2",
  "scikit-learn>=1.4",
  "beautifulsoup4>=4.12",
  "requests>=2.31",
  "langdetect>=1.0",
  "datasketch>=1.6",
  "openai>=1.23",
  "anthropic>=0.25",
  "captum>=0.7",
  "pydantic>=2.7",
  "rich>=13.7",
  "typer>=0.12",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
```

---

## Reproducibility Checklist (README.md must cover)

1. `uv sync` — install all dependencies
2. `uv run scripts/run_scrape.py` — scrape and filter
3. Manual annotation step (instructions for Doccano or BRAT)
4. `uv run scripts/run_agreement.py` — compute IAA
5. `uv run scripts/run_train_baseline.py` — fine-tune baseline
6. `uv run scripts/run_train_enhanced.py` — DAPT + CRF
7. `uv run scripts/run_eval_llm.py` — LLM zero/few-shot
8. `uv run scripts/run_analysis.py` — all evaluation tables + plots

All random seeds fixed via `seed=42` in all trainers and dataset splits.
All results written to `results/` as JSON + CSV.

---

## Final Paper Sections (ACL, 5 pages)

| Section | Content |
|---|---|
| Introduction | Research question, motivation, contributions |
| Related Work | BERT NER, domain adaptation, fictional NER, LLM NER |
| Data | Scraping, filtering stats, annotation process, IAA results |
| Models | Baseline, DAPT, CRF, LLM prompting setup |
| Experiments | Training details, hyperparameters, all evaluation settings |
| Results | Table: P/R/F1 per model × dataset; ablation table; learning curves |
| Analysis | Qualitative errors, token importance, partial match breakdown |
| Conclusion | Answer research question, limitations, future work |
