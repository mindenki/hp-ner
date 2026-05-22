"""EWT NER baseline training — fine-tunes DeBERTaV3 on the EWT split.

Driven entirely by ``configs/baseline.yaml``; called once from
``scripts/prepare_annotation.py::_step_train_ewt`` to produce the checkpoint
that both silver labelling (script 1) and the HP pipelines (script 3) reuse.

Writes:
    outputs/baseline/run_YYYYmmdd_HHMMSS/best_model/
    outputs/baseline/run_YYYYmmdd_HHMMSS/label2id.json
    outputs/baseline/LATEST_RUN.txt
"""
import json
import logging
from datetime import datetime
from pathlib import Path

from src.common.iob2 import read_iob2
from src.modeling.dataset import NERDataset, build_label_vocab
from src.modeling.model import DeBERTaNER
from src.modeling.trainer import TrainConfig, Trainer

logger = logging.getLogger(__name__)


def train_ewt_entrypoint(cfg: dict) -> Path:
    """Train and return the run directory containing best_model/."""
    output_root = Path(cfg["paths"]["output_dir"])
    run_dir = output_root / datetime.now().strftime("run_%Y%m%d_%H%M%S")
    run_dir.mkdir(parents=True, exist_ok=True)
    (output_root / "LATEST_RUN.txt").write_text(run_dir.name, encoding="utf-8")

    train_sents = read_iob2(Path(cfg["paths"]["train"]))
    dev_sents = read_iob2(Path(cfg["paths"]["dev"]))
    label2id, id2label = build_label_vocab(train_sents)
    (run_dir / "label2id.json").write_text(json.dumps(label2id, indent=2), encoding="utf-8")

    max_len = cfg["model"]["max_length"]
    model = DeBERTaNER(cfg["model"]["name"], len(label2id), id2label, label2id)
    Trainer(model, TrainConfig(**cfg["training"]), run_dir).train(
        NERDataset(train_sents, model.tokenizer, label2id, max_len),
        NERDataset(dev_sents, model.tokenizer, label2id, max_len),
    )
    logger.info("train_ewt_entrypoint: best model saved under %s/best_model/", run_dir)
    return run_dir
