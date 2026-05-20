"""Run the 6 HP-NER pipelines: train each, then evaluate on gold test.

Each pipeline trains one or more stages (silver and/or gold_train), starting either
from the EWT-fine-tuned checkpoint or from base DeBERTaV3. For multi-stage pipelines,
the model stays in memory between stages (no intermediate reload). After all stages,
the in-memory model is evaluated on gold_test and metrics + plots are written.

Per-stage Trainer output (incl. learning_curve.json) lives in stage_<i>_<data>/.
The cross-pipeline learning curve is built later by scripts/aggregate_plots.py.

Usage:
    uv run run-pipelines
    uv run run-pipelines --only gold_from_ewt
    uv run run-pipelines --skip silver_from_base --skip silver_then_gold_from_base
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

from baseline.src.dataset import NERDataset, build_label_vocab, read_iob2
from baseline.src.evaluator import Evaluator
from baseline.src.model import DeBERTaNER
from baseline.src.trainer import TrainConfig, Trainer

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

logger = logging.getLogger(__name__)


def _setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[logging.StreamHandler(sys.stdout)],
    )
    logging.getLogger("baseline.src").setLevel(logging.INFO)


def _resolve(path: str) -> Path:
    """Resolve a config path against the project root unless already absolute."""
    p = Path(path)
    return p if p.is_absolute() else _PROJECT_ROOT / p


def _build_hp_label_vocab(gold_train_path: Path) -> tuple[dict[str, int], dict[int, str]]:
    """Build the canonical HP label vocab from the gold train split.

    Used for every pipeline so the model head size is consistent across runs,
    including when loading from the EWT checkpoint (head is re-initialized).
    """
    train_sentences = read_iob2(gold_train_path)
    return build_label_vocab(train_sentences)


def _resolve_ewt_checkpoint(paths: dict[str, str]) -> Path:
    """Resolve the EWT checkpoint directory.

    Primary: ``paths['ewt_checkpoint']`` (relative to project root unless absolute).

    Fallback: if that path doesn't exist and looks like the conventional
    ``outputs/baseline/best_model``, try:
      - outputs/baseline/LATEST_RUN.txt -> <run_name>/best_model
      - newest outputs/baseline/run_*/best_model
    """
    configured = _resolve(paths["ewt_checkpoint"])
    if configured.exists():
        return configured

    # If the baseline outputs folder exists, try to resolve the latest run.
    baseline_outputs = configured.parent if configured.name == "best_model" else configured
    if baseline_outputs.exists() and baseline_outputs.is_dir():
        latest_ptr = baseline_outputs / "LATEST_RUN.txt"
        if latest_ptr.exists():
            run_name = latest_ptr.read_text(encoding="utf-8").strip()
            candidate = baseline_outputs / run_name / "best_model"
            if candidate.exists():
                logger.info(
                    "Resolved EWT checkpoint via LATEST_RUN.txt: %s",
                    candidate,
                )
                return candidate

        run_dirs = sorted(
            (p for p in baseline_outputs.glob("run_*") if p.is_dir()),
            key=lambda p: p.name,
            reverse=True,
        )
        for run_dir in run_dirs:
            candidate = run_dir / "best_model"
            if candidate.exists():
                logger.info(
                    "Resolved EWT checkpoint via newest run dir: %s",
                    candidate,
                )
                return candidate

    raise FileNotFoundError(
        f"EWT checkpoint not found at {configured} (and no fallback baseline run found)."
    )


def _load_starting_model(
    init_from: str,
    paths: dict[str, str],
    model_cfg: dict[str, Any],
    label2id: dict[str, int],
    id2label: dict[int, str],
) -> DeBERTaNER:
    """Construct the starting checkpoint for a pipeline.

    ``init_from == 'base'``            -> fresh DeBERTaV3 with the HP head.
    ``init_from == 'ewt_checkpoint'``  -> load the EWT checkpoint dir as the model_name;
                                          HF re-initializes the classifier head because the
                                          label space differs (3 -> 6 classes).
    """
    if init_from == "base":
        logger.info("Initializing from base DeBERTaV3 (no prior fine-tuning)")
        return DeBERTaNER(
            model_name=model_cfg["name"],
            num_labels=len(label2id),
            id2label=id2label,
            label2id=label2id,
        )
    if init_from == "ewt_checkpoint":
        ckpt_path = _resolve_ewt_checkpoint(paths)
        logger.info(f"Initializing from EWT checkpoint: {ckpt_path}")
        return DeBERTaNER(
            model_name=str(ckpt_path),
            num_labels=len(label2id),
            id2label=id2label,
            label2id=label2id,
        )
    raise ValueError(f"Unknown init_from: {init_from!r}")


def _train_stage(
    model: DeBERTaNER,
    stage_data_path: Path,
    dev_path: Path,
    label2id: dict[str, int],
    max_length: int,
    train_cfg: TrainConfig,
    stage_output_dir: Path,
) -> None:
    """Train one pipeline stage in place — the model is updated by reference."""
    logger.info(f"Stage data: {stage_data_path}  output: {stage_output_dir}")
    train_sentences = read_iob2(stage_data_path)
    dev_sentences = read_iob2(dev_path)
    train_dataset = NERDataset(train_sentences, model.tokenizer, label2id, max_length)
    dev_dataset = NERDataset(dev_sentences, model.tokenizer, label2id, max_length)

    trainer = Trainer(model, train_cfg, stage_output_dir)
    trainer.train(train_dataset, dev_dataset)


def _evaluate_pipeline(
    pipeline_name: str,
    model: DeBERTaNER,
    gold_test_path: Path,
    output_dir: Path,
    device: str,
    eval_batch_size: int,
    max_length: int,
    label2id: dict[str, int],
) -> dict[str, Any]:
    """Run final evaluation on gold_test using the in-memory model."""
    test_sentences = read_iob2(gold_test_path)
    test_dataset = NERDataset(test_sentences, model.tokenizer, label2id, max_length)

    evaluator = Evaluator(model, device, eval_batch_size)
    predictions = evaluator.predict(test_dataset)

    pred_path = output_dir / "predictions" / "test.iob2"
    evaluator.write_predictions(test_dataset, predictions, pred_path)
    evaluator.run_span_f1(gold_test_path, pred_path)

    gold_labels: list[list[str]] = [s.labels for s in test_sentences]
    record = evaluator.performance_metrics(
        gold=gold_labels,
        pred=predictions,
        output_dir=output_dir,
        model_name=pipeline_name,
    )
    return record


def _run_one_pipeline(
    pipeline: dict[str, Any],
    cfg: dict[str, Any],
    label2id: dict[str, int],
    id2label: dict[int, str],
) -> dict[str, Any]:
    """Run one pipeline end-to-end. Returns the final metrics record."""
    name: str = pipeline["name"]
    init_from: str = pipeline["init_from"]
    stages: list[dict[str, str]] = pipeline["stages"]

    paths: dict[str, str] = cfg["paths"]
    model_cfg: dict[str, Any] = cfg["model"]
    train_cfg_dict: dict[str, Any] = cfg["training"]
    eval_cfg: dict[str, Any] = cfg["evaluation"]

    output_root = _resolve(paths["output_root"])
    run_name = datetime.now().strftime("run_%Y%m%d_%H%M%S")
    pipeline_dir = output_root / name / run_name
    pipeline_dir.mkdir(parents=True, exist_ok=True)
    logger.info(f"=== Pipeline '{name}' — output: {pipeline_dir} ===")

    (pipeline_dir / "label2id.json").write_text(json.dumps(label2id, indent=2), encoding="utf-8")
    (output_root / name / "LATEST_RUN.txt").write_text(run_name, encoding="utf-8")

    train_cfg = TrainConfig(
        num_epochs=train_cfg_dict["num_epochs"],
        learning_rate=train_cfg_dict["learning_rate"],
        batch_size=train_cfg_dict["batch_size"],
        warmup_ratio=train_cfg_dict["warmup_ratio"],
        weight_decay=train_cfg_dict["weight_decay"],
        device=train_cfg_dict["device"],
        seed=train_cfg_dict["seed"],
    )
    max_length: int = model_cfg["max_length"]
    dev_path = _resolve(paths["gold_dev"])

    model = _load_starting_model(init_from, paths, model_cfg, label2id, id2label)

    for stage_idx, stage in enumerate(stages, start=1):
        data_key = stage["data"]
        stage_data_path = _resolve(paths[data_key])
        stage_dir = pipeline_dir / f"stage_{stage_idx}_{data_key}"
        _train_stage(
            model=model,
            stage_data_path=stage_data_path,
            dev_path=dev_path,
            label2id=label2id,
            max_length=max_length,
            train_cfg=train_cfg,
            stage_output_dir=stage_dir,
        )
        # In-memory continuation between stages: no reload.

    record = _evaluate_pipeline(
        pipeline_name=name,
        model=model,
        gold_test_path=_resolve(paths["gold_test"]),
        output_dir=pipeline_dir,
        device=train_cfg_dict["device"],
        eval_batch_size=eval_cfg["batch_size"],
        max_length=max_length,
        label2id=label2id,
    )
    logger.info(f"=== Pipeline '{name}' complete — test F1={record['overall']['f1']:.4f} ===")
    return record


def main() -> None:
    _setup_logging()
    parser = argparse.ArgumentParser(description="Run the 6 HP-NER pipelines.")
    parser.add_argument(
        "--config",
        default=str(_PROJECT_ROOT / "baseline" / "configs" / "pipelines.yaml"),
        help="Path to pipelines.yaml",
    )
    parser.add_argument(
        "--only",
        action="append",
        default=[],
        help="Run only the named pipeline (repeatable). Default: run all.",
    )
    parser.add_argument(
        "--skip",
        action="append",
        default=[],
        help="Skip the named pipeline (repeatable).",
    )
    args = parser.parse_args()

    logger.info(f"Loading config from: {args.config}")
    with open(args.config, encoding="utf-8") as fh:
        cfg = yaml.safe_load(fh)

    label2id, id2label = _build_hp_label_vocab(_resolve(cfg["paths"]["gold_train"]))
    logger.info(f"HP label vocab: {len(label2id)} labels — {list(label2id.keys())}")

    pipelines: list[dict[str, Any]] = cfg["pipelines"]
    if args.only:
        only = set(args.only)
        pipelines = [p for p in pipelines if p["name"] in only]
    if args.skip:
        skip = set(args.skip)
        pipelines = [p for p in pipelines if p["name"] not in skip]

    if not pipelines:
        logger.error("No pipelines selected — check --only / --skip filters.")
        sys.exit(1)

    summary: list[dict[str, Any]] = []
    for pipeline in pipelines:
        try:
            record = _run_one_pipeline(pipeline, cfg, label2id, id2label)
            summary.append({
                "name": pipeline["name"],
                "status": "ok",
                "test_f1": record["overall"]["f1"],
            })
        except Exception:
            logger.error(f"Pipeline '{pipeline['name']}' FAILED:\n{traceback.format_exc()}")
            summary.append({"name": pipeline["name"], "status": "failed"})

    logger.info("=" * 70)
    logger.info("All pipelines finished. Summary:")
    for row in summary:
        logger.info(f"  {row}")


if __name__ == "__main__":
    main()
