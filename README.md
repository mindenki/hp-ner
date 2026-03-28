# Baseline: DeBERTaV3 NER on EWT

Fine-tunes `microsoft/deberta-v3-base` on the English Web Treebank (EWT) for Named Entity Recognition.
This serves as the course baseline submission and as the zero-shot comparison model for the Harry Potter NER experiments.

Entities recognized: **PER** (person), **LOC** (location), **ORG** (organization) in IOB2 format.

---

## Repository Structure

```
hp-ner/
├── pyproject.toml               # Project metadata and dependencies (uv)
├── uv.lock                      # Pinned dependency versions
├── baseline/
│   ├── configs/
│   │   └── baseline.yaml        # All hyperparameters and paths
│   ├── scripts/
│   │   ├── train.py             # Training entrypoint
│   │   └── evaluate.py          # Evaluation + span_f1.py runner
│   └── src/
│       ├── dataset.py           # IOB2 reader + PyTorch Dataset
│       ├── model.py             # DeBERTaV3 token classification model
│       ├── trainer.py           # Training loop
│       └── evaluator.py         # Inference + prediction writer
├── data/                        # Place EWT .iob2 files here
│   ├── en_ewt-ud-train.iob2
│   ├── en_ewt-ud-dev.iob2
│   └── en_ewt-ud-test-masked.iob2
├── outputs/                     # Model checkpoints and predictions (git-ignored)
│   └── baseline/
│       ├── best_model/          # Saved after training
│       ├── predictions/         # Written by evaluate.py
│       ├── label2id.json        # Label vocabulary (built from training set)
│       └── training_history.json
└── span_f1.py                   # Place course-provided script here (project root)
```

---

## Prerequisites

- **Python >= 3.11**
- **[uv](https://docs.astral.sh/uv/)** — fast Python package manager

Install `uv` if you don't have it:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

---

## Setup

### 1. Sync dependencies

From the project root, install all dependencies into a managed virtual environment:

```bash
uv sync
```

This creates a `.venv/` directory and installs all packages pinned in `uv.lock`.

> **GPU default:** This project is configured so `torch` is resolved from the official PyTorch CUDA 12.8 index when syncing with `uv`, enabling CUDA on supported NVIDIA systems.
>
> **CPU-only fallback (optional):** If you intentionally want CPU-only PyTorch, reinstall torch in the environment with:
>
> `uv pip install --python .venv/bin/python --index-url https://download.pytorch.org/whl/cpu --force-reinstall torch`

### 2. Activate the virtual environment

```bash
source .venv/bin/activate
```

To deactivate later:

```bash
deactivate
```

> **Note:** You can skip activation entirely and prefix commands with `uv run` instead (see below). `uv run` automatically uses the managed environment.

### 3. Place data files

Put the EWT data files in `data/`:

```
data/en_ewt-ud-train.iob2
data/en_ewt-ud-dev.iob2
data/en_ewt-ud-test-masked.iob2
```

Place the course-provided `span_f1.py` at the **project root** (alongside `pyproject.toml`).

---

## Training

With `uv run` (no activation needed):

```bash
uv run train
```

Or with the venv activated:

```bash
python baseline/scripts/train.py
```

Pass `--config path/to.yaml` to override the default config (`baseline/configs/baseline.yaml`).

**What it does:**
- Fine-tunes DeBERTaV3-base on the EWT training set
- Evaluates on the dev set after each epoch (seqeval micro-F1)
- Saves the best checkpoint (by dev F1) to `outputs/baseline/best_model/`
- Saves the label vocabulary to `outputs/baseline/label2id.json`
- Saves training history to `outputs/baseline/training_history.json`

---

## Evaluation

**Dev set** (runs span_f1.py automatically if present):

```bash
uv run evaluate --split dev
```

**Test set** (labels are masked — F1 not computed):

```bash
uv run evaluate --split test
```

Or with the venv activated:

```bash
python baseline/scripts/evaluate.py --split dev
python baseline/scripts/evaluate.py --split test
```

Pass `--config path/to.yaml` to override the default config (`baseline/configs/baseline.yaml`).

Predictions are written to `outputs/baseline/predictions/{split}.iob2` in IOB2 format.

---

## Configuration

All settings live in [baseline/configs/baseline.yaml](baseline/configs/baseline.yaml)

| Parameter | Default | Description |
|---|---|---|
| `model.name` | `microsoft/deberta-v3-base` | HuggingFace model ID |
| `model.max_length` | `128` | Max subword token length (sentences are truncated) |
| `training.num_epochs` | `1` | Number of fine-tuning epochs |
| `training.learning_rate` | `5e-6` | AdamW learning rate |
| `training.batch_size` | `16` | Training batch size |
| `training.warmup_ratio` | `0.1` | Fraction of steps used for linear LR warmup |
| `training.weight_decay` | `0.01` | L2 regularization (applied to non-bias/LayerNorm params) |
| `training.device` | `cpu` | Set to `cuda` if a GPU is available |
| `training.seed` | `42` | Random seed for reproducibility |
| `evaluation.batch_size` | `32` | Inference batch size |
| `paths.output_dir` | `outputs/baseline` | Root output directory |

---

## Notes

- **Subword masking:** Only the first subword token of each word is labeled; continuation subwords are assigned `IGNORED_LABEL_ID = -100` and excluded from loss and evaluation.
- **Truncation:** Sentences longer than `max_length` are truncated. Truncated tokens are predicted as `O` during evaluation.
- **Label vocabulary:** Built from the training set and saved to `outputs/baseline/label2id.json`. The 7 labels are: `O`, `B-PER`, `I-PER`, `B-LOC`, `I-LOC`, `B-ORG`, `I-ORG`.
