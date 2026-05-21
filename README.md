# HP-NER — Named Entity Recognition in the Harry Potter Universe

End-to-end NER pipeline for six fictional entity types
(`CHARACTER`, `LOCATION`, `ORGANIZATION`, `CREATURE`, `SPELL`,
`ARTIFACT`) on text scraped from the Harry Potter Fandom wiki.
Compares a DeBERTaV3 baseline against fine-tuned and silver-to-gold
variants and includes an optional GPT-4o zero-shot reference.

> **Paper:** see `NER_Project_Report.pdf`

---

## Prerequisites

- **Python ≥ 3.11**
- **[uv](https://docs.astral.sh/uv/)** — manages the venv and installs the project editable
- **Docker Desktop** — only needed for the Doccano steps (annotation prep & export)
- **(optional) `OPENAI_API_KEY`** env var — only for `train-and-evaluate --with-llm-reference`

The pipeline runs on **macOS, Linux, and Windows**. Where commands differ, both versions
are shown side-by-side. PowerShell is the recommended shell on Windows.

---

## Installation

### 1. Install `uv`

**macOS / Linux** (bash/zsh):

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

**Windows** (PowerShell):

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

After install, open a new terminal so `uv` is on your `PATH`.

### 2. Clone and sync

```bash
git clone https://github.com/mindenki/hp-ner.git
cd hp-ner
uv sync
```

`uv sync` creates a `.venv/`, installs all dependencies pinned in `uv.lock`, and
installs this project itself in editable mode (so `prepare-annotation`,
`finalize-gold`, `train-and-evaluate` become console commands).

### 3. (Optional) GPT-4o key

If you plan to use the `--with-llm-reference` flag:

**macOS / Linux:**

```bash
export OPENAI_API_KEY=sk-...
```

**Windows (PowerShell):**

```powershell
$env:OPENAI_API_KEY = "sk-..."
```

**Windows (cmd.exe):**

```bat
set OPENAI_API_KEY=sk-...
```

Persist it across sessions by adding it to your shell profile (`~/.zshrc`,
`~/.bashrc`) or PowerShell `$PROFILE`, or set it as a permanent user env var
via System Properties → Environment Variables on Windows.

---

## Reproduce the project end-to-end

Three console scripts, run in order. Each script supports:

- `--only-step STEP` (repeatable) — run only the listed step(s); default = all
- `--force-<step>` — re-run a step whose output already exists

All scripts can be invoked as `uv run <script-name>` from the project root, on
any platform.

---

### 1. `prepare-annotation` — build the corpus and seed Doccano

```bash
uv run prepare-annotation
```

**Steps** (in declaration order):

| Step               | What it does                              | Skipped if                                  |
| ------------------ | ----------------------------------------- | ------------------------------------------- |
| `train_ewt`        | Fine-tunes DeBERTaV3 on EWT NER           | `outputs/baseline/run_*/best_model/` exists |
| `scrape`           | Crawls the HP Fandom wiki                 | `data/raw/wiki_data.jsonl` exists           |
| `clean`            | Sentence-split + normalise                | `data/filtered/` exists                     |
| `build_dict`       | Builds entity dictionary                  | `data/dictionaries/txts/` populated         |
| `silver_label`     | BERT + dictionary tagging                 | `data/silver/hp_silver.jsonl` exists        |
| `select_15k`       | Stratified sample of 15 000 sentences     | `data/selected/silver/hp_15k.jsonl` exists  |
| `select_gold_pool` | Pick 1 250 sentences across 4 buckets     | `data/selected/gold_pool/` populated        |
| `setup_doccano`    | Create 4 Doccano projects + import JSONLs | `--skip-doccano` passed                     |

The `setup_doccano` step needs Doccano running locally. Start it before that
step (or pass `--skip-doccano` to defer):

```bash
cd doccano
docker compose up -d
cd ..
```

> Windows PowerShell users: `cd ..` works the same as on Unix. Avoid the
> `cd doccano && docker compose up -d && cd -` shortcut from older Unix docs;
> chain commands with `;` in PowerShell or run them on separate lines.

When `setup_doccano` finishes it opens `http://localhost:8000` in your default
browser. Log in with the credentials in [doccano/README.md](doccano/README.md).

**Run just one step** (handy when iterating):

```bash
uv run prepare-annotation --only-step silver_label
uv run prepare-annotation --only-step clean --only-step silver_label   # repeatable
uv run prepare-annotation --force-scrape --force-silver                # ignore the skip-if-exists guard
```

---

### 2. Annotate — humans label in Doccano

Each annotator logs into their pre-loaded Doccano project (4 projects were
created by `setup_doccano`, one per annotator) and labels their assigned
sentences using the schema in [annotation_guidelines.md](annotation_guidelines.md).
See [doccano/README.md](doccano/README.md) for the UI walk-through and
keyboard shortcuts.

---

### 3. `finalize-gold` — IAA + merge + write IOB2

```bash
uv run finalize-gold
```

**Steps:**

| Step                  | What it does                                            | Notes                                                                    |
| --------------------- | ------------------------------------------------------- | ------------------------------------------------------------------------ |
| `export_from_doccano` | Pulls JSONL exports from running Doccano                | Needs Doccano up; `--skip-export` if `data/annotated/` already populated |
| `compute_iaa`         | Pairwise Cohen κ per token                              | Hard-fails below 0.7 unless `--allow-low-agreement`                      |
| `merge_gold`          | Majority vote on overlap; interactive prompt on ties    | `--non-interactive` skips conflicts with a warning                       |
| `write_iob2`          | Writes `data/selected/{gold,silver}/{gold,silver}.iob2` | Always last                                                              |

Conflict resolutions are persisted to `data/iaa/overrides.jsonl` so re-runs
are repeatable.

**Common variants:**

```bash
uv run finalize-gold --skip-export                                         # if data/annotated/ is already there
uv run finalize-gold --only-step compute_iaa                               # just the agreement report
uv run finalize-gold --non-interactive --allow-low-agreement               # batch mode
```

---

### 4. `train-and-evaluate` — split + 6 pipelines + eval

```bash
uv run train-and-evaluate
```

**Steps:**

| Step              | What it does                                                   |
| ----------------- | -------------------------------------------------------------- |
| `split_gold`      | Stratified 80/10/10 of `gold.iob2` → `train/dev/test.iob2`     |
| `run_pipelines`   | Trains the six pipelines defined in `configs/pipelines.yaml`   |
| `aggregate_plots` | Cross-pipeline learning-curve PNG + summary CSV                |
| `gpt4o_reference` | GPT-4o zero-shot predictions (requires `--with-llm-reference`) |

**Common variants:**

```bash
uv run train-and-evaluate --with-llm-reference                # add the GPT-4o row
uv run train-and-evaluate --only-pipeline gold_from_ewt       # train one pipeline only
uv run train-and-evaluate --only-step aggregate_plots         # re-build plots without re-training
```

Outputs land under `outputs/pipelines/<name>/run_*/` (per-pipeline checkpoints,
predictions, metrics) and `outputs/aggregate/` (`learning_curves_all.png`,
`summary.csv`).

> **GPU**: on Linux with CUDA 12.8 GPUs, `uv` will install the CUDA build of
> PyTorch automatically via the `pytorch-cu128` index. On macOS / Windows the
> CPU build is used. Training the six pipelines end-to-end on CPU is slow
> (hours); a single GPU is recommended for full runs.

---

## Configuration

All hyperparameters live in YAML files under [configs/](configs/):

- [`baseline.yaml`](configs/baseline.yaml) — EWT baseline training (used by
  `prepare-annotation --only-step train_ewt`)
- [`pipelines.yaml`](configs/pipelines.yaml) — the six HP fine-tuning
  pipelines (used by `train-and-evaluate`)

Edit the YAML, re-run the script — no code changes needed.

---

## Repository layout

```
hp-ner/
├── configs/                           baseline.yaml, pipelines.yaml
├── doccano/                           local docker-compose stack + setup guide
├── llm_reference/                     GPT-4o zero-shot reference (predict.py + prompt.py)
├── legacy/                            Azure-VM artefacts (not used by the pipeline)
├── scripts/                           the 3 orchestrator entry points
│   ├── prepare_annotation.py
│   ├── finalize_gold.py
│   └── train_and_evaluate.py
├── src/                               library code (namespace package, no __init__.py)
│   ├── common/                        IOB2 reader/writer, span helpers, logging
│   ├── modeling/                      DeBERTa NER: dataset, model, trainer, evaluator, splitter, plots
│   ├── scraping/   preprocessing/     wiki crawler + cleaner + sentence filter
│   ├── dict_builder/                  entity-dictionary builder
│   ├── silver_labeling/               BERT + dictionary silver tagger
│   ├── selection/                     stratified sampling + 4-bucket gold pool
│   ├── annotation/                    Doccano client + merge logic
│   ├── iaa/                           Cohen κ agreement
│   └── baseline/                      EWT NER baseline trainer
├── tests/                             pytest smoke tests + fixtures
└── pyproject.toml
```

---
