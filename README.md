# HP-NER: Named Entity Recognition for the Harry Potter Universe

Fine-tunes `microsoft/deberta-v3-base` on the English Web Treebank (EWT) as a course baseline, then builds a Harry Potter–specific NER corpus via wiki scraping, dictionary-guided silver labeling, and manual annotation — targeting six entity types: **CHARACTER, LOCATION, ORGANIZATION, CREATURE, SPELL, ARTIFACT**.

---

## Repository Structure

```
hp-ner/
├── baseline/                        # EWT baseline (DeBERTa)
│   ├── configs/baseline.yaml        # Hyperparameters and paths
│   ├── scripts/
│   │   ├── train.py                 # Training entrypoint
│   │   └── evaluate.py              # Evaluation + span_f1.py runner
│   └── src/
│       ├── dataset.py               # IOB2 reader + PyTorch Dataset
│       ├── model.py                 # DeBERTa token classification wrapper
│       ├── trainer.py               # Training loop
│       └── evaluator.py             # Inference + prediction writer
├── src/
│   ├── preprocessing/
│   │   └── iob2.py                  # Shared IOB2Reader / IOB2Writer
│   ├── scraping/
│   │   ├── scraper.py               # WikiScraper (requests + BeautifulSoup4)
│   │   └── cleaner.py               # Text cleaner + sentencizer
│   ├── dict_builder/
│   │   ├── categories.py            # HP Fandom category list
│   │   ├── category_crawler.py      # Crawls wiki categories → canonical names
│   │   ├── alias_extractor.py       # Scrapes infobox aliases per entity
│   │   ├── category_cleaner.py      # Deduplication + casing normalization
│   │   └── txt_writer.py            # Writes per-label .txt dict files
│   └── silver_labeling/
│       ├── entity_dict.py           # Greedy longest-match dictionary lookup
│       ├── bert_tagger.py           # Loads baseline model, maps EWT→HP labels
│       ├── merger.py                # Merges dict + BERT predictions
│       ├── tokenizer.py             # spaCy tokenizer wrapper
│       └── stats.py                 # Coverage / conflict statistics
├── scripts/
│   ├── run_scrape.py                # Run WikiScraper → data/raw/
│   ├── run_category_crawler.py      # Build canonical entity dictionary
│   ├── run_alias_scraper.py         # Enrich dictionary with aliases
│   ├── run_writer.py                # Write .txt dict files for silver labeling
│   └── run_silver_label.py          # Run full silver labeling pipeline
├── data/
│   ├── en_ewt-ud-train.iob2         # EWT training set
│   ├── en_ewt-ud-dev.iob2           # EWT dev set
│   ├── en_ewt-ud-test-masked.iob2   # EWT test set (labels masked)
│   ├── raw/                         # Scraped wiki .jsonl (git-ignored)
│   ├── cleaned/                     # Cleaned sentences .jsonl (git-ignored)
│   ├── filtered/                    # Filtered sentences (git-ignored)
│   ├── dictionaries/                # hp_canonical.json, hp_aliases.json, txts/
│   ├── silver/                      # Silver-labeled .jsonl (git-ignored)
│   ├── annotated/                   # Per-annotator gold IOB2 files
│   └── merged/                      # Adjudicated gold standard
├── outputs/                         # Model checkpoints and predictions
│   └── baseline/
│       └── run_YYYYmmdd_HHMMSS/
│           ├── best_model/          # Saved DeBERTa checkpoint (git-lfs)
│           ├── predictions/         # dev.iob2, test.iob2
│           ├── label2id.json
│           └── training_history.json
├── span_f1.py                       # Course-provided evaluation script
└── pyproject.toml                   # UV-managed dependencies
```

---

## Prerequisites

- **Python >= 3.11**
- **[uv](https://docs.astral.sh/uv/)** — fast Python package manager
- **[git-lfs](https://git-lfs.com/)** — required to download saved model weights

### Install uv

**macOS / Linux**
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

**Windows (PowerShell)**
```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

### Install git-lfs

**macOS**
```bash
brew install git-lfs
```

**Linux**
```bash
sudo apt install git-lfs   # Debian/Ubuntu
sudo dnf install git-lfs   # Fedora
```

**Windows** — download the installer from [git-lfs.com](https://git-lfs.com/).

---

## Setup

### 1. Clone with LFS

If you want the pre-trained model weights included, pull LFS objects after cloning:

```bash
git clone https://github.com/mindenki/hp-ner.git
cd hp-ner
git lfs pull
```

> **Skip LFS:** If you only want the code and intend to train from scratch, a plain `git clone` is enough — LFS objects are downloaded on demand only when you run `git lfs pull`.

### 2. Install dependencies

```bash
uv sync
```

This creates `.venv/` and installs all pinned dependencies.

> **GPU:** PyTorch is resolved from the CUDA 12.8 index by default. On a CPU-only machine you can override:
> ```bash
> uv pip install --python .venv/bin/python \
>   --index-url https://download.pytorch.org/whl/cpu \
>   --force-reinstall torch
> ```

### 3. Activate the virtual environment

```bash
source .venv/bin/activate   # macOS / Linux
.venv\Scripts\activate      # Windows
```

Or prefix every command with `uv run` to skip activation entirely.

---

## EWT Baseline

Fine-tunes DeBERTa-v3-base on EWT for standard NER (PER / LOC / ORG). This is the course submission and the zero-shot starting point for HP experiments.

### Train

```bash
uv run train
# or
python baseline/scripts/train.py
```

Pass `--config path/to.yaml` to override `baseline/configs/baseline.yaml`.

**What it does:**
- Fine-tunes on EWT train, evaluates on EWT dev after each epoch (seqeval micro-F1)
- Saves each run to `outputs/baseline/run_YYYYmmdd_HHMMSS/`
- Saves best checkpoint (by dev F1) to `run_.../best_model/`
- Updates `outputs/baseline/LATEST_RUN.txt`

### Evaluate

```bash
# Dev set (runs span_f1.py automatically if present)
uv run evaluate --split dev

# Specific run
uv run evaluate --split dev --run run_YYYYmmdd_HHMMSS

# Test set (labels masked — no F1 computed)
uv run evaluate --split test
```

Predictions are written to `outputs/baseline/run_.../predictions/{split}.iob2`.

### Configuration

All settings in `baseline/configs/baseline.yaml`:

| Parameter | Default | Description |
|---|---|---|
| `model.name` | `microsoft/deberta-v3-base` | HuggingFace model ID |
| `model.max_length` | `128` | Max subword token length |
| `training.num_epochs` | `1` | Fine-tuning epochs |
| `training.learning_rate` | `5e-6` | AdamW learning rate |
| `training.batch_size` | `16` | Training batch size |
| `training.warmup_ratio` | `0.1` | Linear LR warmup fraction |
| `training.weight_decay` | `0.01` | L2 regularization |
| `training.device` | `cpu` | Set to `cuda` for GPU |
| `training.seed` | `42` | Random seed |
| `evaluation.batch_size` | `32` | Inference batch size |

### Using the pre-trained checkpoint

The baseline checkpoint committed to this repo via git-lfs can be used directly for inference without re-training:

```bash
git lfs pull   # if not already done
uv run evaluate --split dev
```

---

## HP NER Pipeline — Phase 1

The full pipeline runs in order: **scrape → clean → build dictionary → silver label**.

### Step 1 — Scrape the HP Fandom Wiki

```bash
python scripts/run_scrape.py
```

Recursively crawls HP Fandom wiki pages (depth=2 by default) and writes raw `.jsonl` to `data/raw/wiki_data.jsonl`. Each record:

```json
{"url": "...", "title": "Harry Potter", "paragraphs": ["...", "..."]}
```

Edit `scripts/run_scrape.py` to change seed URLs, crawl depth, or output path.

### Step 2 — Clean the scraped text

`src/scraping/cleaner.py` strips wiki markup, normalizes Unicode, and sentencizes paragraphs using spaCy. Import it directly or adapt `clean_dataset()`:

```python
from src.scraping.cleaner import clean_dataset

cleaned, dropped = clean_dataset(
    input_path="data/raw/wiki_data.jsonl",
    output_path="data/cleaned/wiki_data_clean.jsonl",
)
print(f"Kept {len(cleaned)}, dropped {len(dropped)}")
```

Output `paragraphs` becomes a list of sentence lists.

### Step 3 — Build the entity dictionary

Run these three scripts in sequence:

```bash
# 1. Crawl HP Fandom categories → data/dictionaries/hp_canonical.json
python scripts/run_category_crawler.py

# 2. Scrape infobox aliases for each entity → data/dictionaries/hp_aliases.json
python scripts/run_alias_scraper.py

# 3. Write per-label .txt files for the greedy matcher
#    → data/dictionaries/txts/{CHARACTER,LOCATION,ORGANIZATION,CREATURE,SPELL,ARTIFACT}.txt
python scripts/run_writer.py
```

The `.txt` format (used by `src/silver_labeling/entity_dict.py`):
```
Harry Potter
>The Boy Who Lived
>Harry
Hermione Granger
>Hermione
```
Canonical name first, aliases prefixed with `>`, sorted longest-first for greedy matching.

### Step 4 — Silver labeling

Combines dictionary lookup (high precision for SPELL/ARTIFACT/CREATURE) with the baseline DeBERTa model (covers CHARACTER/LOCATION/ORGANIZATION):

```bash
python scripts/run_silver_label.py
# or with options:
python scripts/run_silver_label.py --batch-size 64 --run run_YYYYmmdd_HHMMSS
```

Requires a trained baseline checkpoint in `outputs/baseline/`. Output goes to `data/silver/`.

Each output record:
```json
{
  "tokens": ["Harry", "Potter", "cast", "Expelliarmus"],
  "silver_labels": ["B-CHARACTER", "I-CHARACTER", "O", "B-SPELL"],
  "silver_source": ["dict", "dict", "O", "dict"]
}
```

---

## IOB2 Utilities

`src/preprocessing/iob2.py` is the shared reader/writer used throughout the project.

```python
from src.preprocessing.iob2 import IOB2Reader, IOB2Writer, Sentence
from pathlib import Path

# Read generic 2-column IOB2 (token\tlabel)
sentences = IOB2Reader(mode="generic", validate=True).read(Path("data/annotated/file.iob2"))

# Read EWT 5-column format (skips # comment lines)
sentences = IOB2Reader(mode="ewt", validate=False).read(Path("data/en_ewt-ud-dev.iob2"))

# Write generic IOB2
IOB2Writer().write(sentences, Path("data/output.iob2"))

# Write EWT prediction format (idx\ttoken\tlabel) — compatible with span_f1.py
IOB2Writer(mode="ewt").write(sentences, Path("outputs/predictions/dev.iob2"))
```

`validate=True` raises `ValueError` on illegal IOB2 transitions (e.g., `O → I-X`).  
`fix_transitions=True` on `IOB2Writer` silently rewrites illegal `I-` labels to `B-` instead of raising.

---

## Reproducibility

Full pipeline from scratch:

```bash
# 1. Install
uv sync

# 2. Scrape
python scripts/run_scrape.py

# 3. Clean (adapt paths in cleaner.py)
python -c "from src.scraping.cleaner import clean_dataset; clean_dataset('data/raw/wiki_data.jsonl', 'data/cleaned/wiki_data_clean.jsonl')"

# 4. Build entity dictionary
python scripts/run_category_crawler.py
python scripts/run_alias_scraper.py
python scripts/run_writer.py

# 5. Train EWT baseline (needed for silver labeling)
uv run train

# 6. Silver label
python scripts/run_silver_label.py

# 7. (Manual) Annotate in Doccano using silver labels as pre-annotations

# 8. Evaluate baseline
uv run evaluate --split dev
uv run evaluate --split test
```

All random seeds fixed at `seed=42`.

---

## Notes

- **Subword masking:** Only the first subword token of each word is labeled; continuation subwords get `IGNORED_LABEL_ID = -100` and are excluded from loss and evaluation.
- **Truncation:** Sentences longer than `max_length` are truncated; truncated tokens are predicted as `O`.
- **Label vocabulary:** Built from the training set and saved to `run_.../label2id.json`. EWT labels: `O, B-PER, I-PER, B-LOC, I-LOC, B-ORG, I-ORG`.
- **git-lfs:** `outputs/` is in `.gitignore` by default. Model checkpoints committed to this repo were force-added and tracked via git-lfs. Use `git lfs pull` to download them; use `git add -f` to commit new ones.
