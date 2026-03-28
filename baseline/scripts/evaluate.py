"""Evaluate a trained DeBERTaNER checkpoint on dev or test.

Usage (from project root):
    uv run evaluate --split dev                        # uses default config
    uv run evaluate --split test                       # uses default config
    uv run evaluate --split dev --config path/to.yaml  # override config
"""
from __future__ import annotations # for Anis' request

import argparse
import json
import logging
import sys
from pathlib import Path

import yaml

# Add baseline/ to sys.path so `src` package is importable
_BASELINE_DIR = Path(__file__).resolve().parent.parent
_PROJECT_ROOT = _BASELINE_DIR.parent
sys.path.insert(0, str(_BASELINE_DIR))

from src.dataset import NERDataset, read_iob2  # noqa: E402
from src.evaluator import Evaluator  # noqa: E402
from src.model import DeBERTaNER  # noqa: E402

logger = logging.getLogger(__name__)


def _setup_logging() -> None:
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[logging.StreamHandler(sys.stdout)],
    )
    logging.getLogger("transformers").setLevel(logging.DEBUG)


def main() -> None:
    _setup_logging()

    parser = argparse.ArgumentParser(description="Evaluate DeBERTaNER on dev or test split.")
    parser.add_argument(
        "--config",
        default=str(_BASELINE_DIR / "configs" / "baseline.yaml"),
        help="Path to baseline.yaml (default: baseline/configs/baseline.yaml)",
    )
    parser.add_argument(
        "--split",
        required=True,
        choices=["dev", "test"],
        help="Which split to evaluate",
    )
    args = parser.parse_args()

    logger.info(f"Loading config from: {args.config}")
    with open(args.config, encoding="utf-8") as fh:
        cfg = yaml.safe_load(fh)

    output_dir = _PROJECT_ROOT / cfg["paths"]["output_dir"]
    split_path = _PROJECT_ROOT / cfg["paths"][args.split]
    device: str = cfg["training"]["device"]
    eval_batch_size: int = cfg["evaluation"]["batch_size"]

    # Load label vocab saved during training.
    vocab_path = output_dir / "label2id.json"
    if not vocab_path.exists():
        logger.error(f"label2id.json not found at {vocab_path} — run train.py first")
        sys.exit(1)
    label2id = json.loads(vocab_path.read_text(encoding="utf-8"))
    logger.info(f"Loaded label vocabulary: {len(label2id)} labels")

    checkpoint_path = output_dir / "best_model"
    if not checkpoint_path.exists():
        logger.error(f"No checkpoint found at {checkpoint_path} — run train.py first")
        sys.exit(1)

    model = DeBERTaNER.load(checkpoint_path)

    logger.info(f"Loading {args.split} split from: {split_path}")
    dataset = NERDataset(read_iob2(split_path), model.tokenizer, label2id, cfg["model"]["max_length"])

    evaluator = Evaluator(model, device, eval_batch_size)
    predictions = evaluator.predict(dataset)

    pred_path = output_dir / "predictions" / f"{args.split}.iob2"
    evaluator.write_predictions(dataset, predictions, pred_path)

    if args.split == "dev":
        # Gold labels are available on dev — run span_f1.py for the official metric.
        evaluator.run_span_f1(split_path, pred_path)
    else:
        logger.info("Test labels are masked — predictions written, no F1 computed")


if __name__ == "__main__":
    main()
