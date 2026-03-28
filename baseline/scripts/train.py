"""Fine-tune DeBERTaV3 on EWT NER.

Usage (from project root):
    uv run train                        # uses default config (baseline/configs/baseline.yaml)
    uv run train --config path/to.yaml  # override config
"""
from __future__ import annotations # for Anis' request

import argparse
import json
import logging
import sys
from pathlib import Path

import yaml # to read config from yaml to python dict

_BASELINE_DIR = Path(__file__).resolve().parent.parent
_PROJECT_ROOT = _BASELINE_DIR.parent
# Add baseline/ to sys.path so 'src' package is importable.
sys.path.insert(0, str(_BASELINE_DIR))

from src.dataset import NERDataset, build_label_vocab, read_iob2  # noqa: E402
from src.model import DeBERTaNER  # noqa: E402
from src.trainer import TrainConfig, Trainer  # noqa: E402

logger = logging.getLogger(__name__)


def _setup_logging() -> None:
    """Configure logging to output to stdout with a consistent format."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[logging.StreamHandler(sys.stdout)],
    )
    logging.getLogger("transformers").setLevel(logging.INFO)


def main() -> None:
    _setup_logging()

    parser = argparse.ArgumentParser(description="Fine-tune DeBERTaV3 on EWT NER.")
    parser.add_argument(
        "--config",
        default=str(_BASELINE_DIR / "configs" / "baseline.yaml"),
        help="Path to baseline.yaml (default: baseline/configs/baseline.yaml)",
    )
    args = parser.parse_args()

    logger.info(f"Loading config from: {args.config}")
    with open(args.config, encoding="utf-8") as fh:
        cfg = yaml.safe_load(fh)

    # Resolve data paths relative to project root.
    train_path = _PROJECT_ROOT / cfg["paths"]["train"]
    dev_path = _PROJECT_ROOT / cfg["paths"]["dev"]
    output_dir = _PROJECT_ROOT / cfg["paths"]["output_dir"]
    output_dir.mkdir(parents=True, exist_ok=True)

    model_name: str = cfg["model"]["name"]
    max_length: int = cfg["model"]["max_length"]
    train_cfg = cfg["training"]

    logger.info(f"Loading training data from: {train_path}")
    train_sentences = read_iob2(train_path)
    logger.info(f"Loading dev data from: {dev_path}")
    dev_sentences = read_iob2(dev_path)

    logger.info("Building label vocab from training data")
    label2id, id2label = build_label_vocab(train_sentences)

    vocab_path = output_dir / "label2id.json"
    vocab_path.write_text(json.dumps(label2id, indent=2), encoding="utf-8")
    logger.info(f"Label vocab saved to: {vocab_path}")

    logger.info(f"Initializing DeBERTaNER with model name: {model_name}")
    model = DeBERTaNER(
        model_name=model_name,
        num_labels=len(label2id),
        id2label=id2label,
        label2id=label2id,
    )

    logger.info(f"Tokenizing training dataset with max_length={max_length}")
    train_dataset = NERDataset(train_sentences, model.tokenizer, label2id, max_length)
    logger.info(f"Tokenizing dev dataset with max_length={max_length}")
    dev_dataset = NERDataset(dev_sentences, model.tokenizer, label2id, max_length)

    logger.info("Initializing config")
    config = TrainConfig(
        num_epochs=train_cfg["num_epochs"],
        learning_rate=train_cfg["learning_rate"],
        batch_size=train_cfg["batch_size"],
        warmup_ratio=train_cfg["warmup_ratio"],
        weight_decay=train_cfg["weight_decay"],
        device=train_cfg["device"],
        seed=train_cfg["seed"],
    )

    logger.info("Initializing trainer")
    trainer = Trainer(model, config, output_dir)
    logger.info("Starting training")
    trainer.train(train_dataset, dev_dataset)


if __name__ == "__main__":
    main()
