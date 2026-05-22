"""Modeling orchestration for scripts/train_and_evaluate.py.

Entry points:
  * run_pipelines_entrypoint(config_path, only=..., skip=...)
       - run the six HP pipelines defined in configs/pipelines.yaml.
  * aggregate_plots_entrypoint(runs_root, output_dir)
       - cross-pipeline learning-curve PNG + summary CSV.
"""
import csv
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

from src.common.iob2 import read_iob2
from src.modeling.dataset import NERDataset, build_label_vocab
from src.modeling.evaluator import Evaluator
from src.modeling.model import DeBERTaNER
from src.modeling.plots import plot_learning_curves_aggregate
from src.modeling.trainer import TrainConfig, Trainer

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# EWT checkpoint resolution (used by pipelines with init_from=ewt_checkpoint)
# ---------------------------------------------------------------------------

def _resolve_ewt_checkpoint(paths: dict) -> Path:
    configured = Path(paths["ewt_checkpoint"])
    if configured.exists():
        return configured
    base = configured.parent if configured.name == "best_model" else configured
    if base.exists():
        ptr = base / "LATEST_RUN.txt"
        if ptr.exists():
            cand = base / ptr.read_text(encoding="utf-8").strip() / "best_model"
            if cand.exists():
                return cand
        for run in sorted(base.glob("run_*"), reverse=True):
            cand = run / "best_model"
            if cand.exists():
                return cand
    raise FileNotFoundError(f"EWT checkpoint not at {configured}")


# ---------------------------------------------------------------------------
# Pipeline runner
# ---------------------------------------------------------------------------

def _run_one_pipeline(
    pipeline: dict,
    cfg: dict,
    label2id: dict[str, int],
    id2label: dict[int, str],
) -> dict:
    """Multi-stage in-memory pipeline; final eval on gold_test. Returns metrics."""
    name = pipeline["name"]
    paths = cfg["paths"]
    model_cfg = cfg["model"]
    train_cfg_dict = cfg["training"]
    eval_cfg = cfg["evaluation"]

    output_root = Path(paths["output_root"])
    run_name = datetime.now().strftime("run_%Y%m%d_%H%M%S")
    pipeline_dir = output_root / name / run_name
    pipeline_dir.mkdir(parents=True, exist_ok=True)
    (pipeline_dir / "label2id.json").write_text(json.dumps(label2id, indent=2), encoding="utf-8")
    (output_root / name / "LATEST_RUN.txt").write_text(run_name, encoding="utf-8")

    train_cfg = TrainConfig(
        **{k: train_cfg_dict[k] for k in TrainConfig.__dataclass_fields__}
    )

    init_from = pipeline["init_from"]
    if init_from == "base":
        model = DeBERTaNER(model_cfg["name"], len(label2id), id2label, label2id)
    elif init_from == "ewt_checkpoint":
        ckpt = _resolve_ewt_checkpoint(paths)
        model = DeBERTaNER(str(ckpt), len(label2id), id2label, label2id)
    else:
        raise ValueError(f"unknown init_from: {init_from!r}")

    max_len = model_cfg["max_length"]
    dev = read_iob2(Path(paths["gold_dev"]))
    for i, stage in enumerate(pipeline["stages"], start=1):
        data_key = stage["data"]
        train_data = read_iob2(Path(paths[data_key]))
        Trainer(model, train_cfg, pipeline_dir / f"stage_{i}_{data_key}").train(
            NERDataset(train_data, model.tokenizer, label2id, max_len),
            NERDataset(dev, model.tokenizer, label2id, max_len),
        )

    test = read_iob2(Path(paths["gold_test"]))
    test_ds = NERDataset(test, model.tokenizer, label2id, max_len)
    evaluator = Evaluator(model, train_cfg.device, eval_cfg["batch_size"])
    preds = evaluator.predict(test_ds)
    evaluator.write_predictions(test_ds, preds, pipeline_dir / "predictions" / "test.iob2")
    return evaluator.performance_metrics(
        gold=[s.labels for s in test],
        pred=preds,
        output_dir=pipeline_dir,
        model_name=name,
    )


def run_pipelines_entrypoint(
    config_path: Path,
    *,
    only: list[str] | None = None,
    skip: list[str] | None = None,
) -> None:
    """Train every pipeline in ``configs/pipelines.yaml`` (filtered by ``only``/``skip``)."""
    cfg = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    label2id, id2label = build_label_vocab(read_iob2(Path(cfg["paths"]["gold_train"])))
    pipelines = cfg["pipelines"]
    if only:
        pipelines = [p for p in pipelines if p["name"] in set(only)]
    if skip:
        pipelines = [p for p in pipelines if p["name"] not in set(skip)]
    for p in pipelines:
        try:
            _run_one_pipeline(p, cfg, label2id, id2label)
        except Exception:
            logger.exception("pipeline %s failed", p["name"])


# ---------------------------------------------------------------------------
# Aggregate plot + summary CSV
# ---------------------------------------------------------------------------

def _latest_run_dir(pipeline_dir: Path) -> Path | None:
    pointer = pipeline_dir / "LATEST_RUN.txt"
    if pointer.exists():
        run = pipeline_dir / pointer.read_text(encoding="utf-8").strip()
        if run.exists():
            return run
        logger.warning(
            "LATEST_RUN.txt for %s points to missing folder: %s", pipeline_dir.name, run,
        )
    candidates = sorted(
        (p for p in pipeline_dir.glob("run_*") if p.is_dir()),
        key=lambda p: p.name,
        reverse=True,
    )
    return candidates[0] if candidates else None


def _final_stage_curve(run_dir: Path) -> list[dict] | None:
    stages = sorted(
        (p for p in run_dir.glob("stage_*_*") if p.is_dir()),
        key=lambda p: p.name,
    )
    if not stages:
        logger.warning("No stage subdirs found under %s", run_dir)
        return None
    curve_path = stages[-1] / "learning_curve.json"
    if not curve_path.exists():
        logger.warning("Missing learning_curve.json at %s", curve_path)
        return None
    return json.loads(curve_path.read_text(encoding="utf-8"))


def _last_metrics(run_dir: Path) -> dict[str, Any] | None:
    path = run_dir / "metrics.jsonl"
    if not path.exists():
        logger.warning("Missing metrics.jsonl at %s", path)
        return None
    last_line: str | None = None
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            stripped = line.strip()
            if stripped:
                last_line = stripped
    return json.loads(last_line) if last_line else None


def _write_summary_csv(rows: list[dict[str, Any]], output_path: Path) -> None:
    fieldnames = [
        "pipeline", "stages",
        "final_train_loss", "final_dev_f1",
        "test_precision", "test_recall", "test_f1", "test_accuracy",
    ]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in fieldnames})
    logger.info("Wrote aggregate summary to %s", output_path)


def aggregate_plots_entrypoint(runs_root: Path, output_dir: Path) -> None:
    """Build the cross-pipeline learning-curve PNG + summary CSV."""
    if not runs_root.exists():
        logger.error("runs-root does not exist: %s", runs_root)
        return

    pipeline_dirs = sorted(p for p in runs_root.iterdir() if p.is_dir())
    if not pipeline_dirs:
        logger.error("No pipeline directories under %s", runs_root)
        return

    curves: dict[str, list[dict]] = {}
    rows: list[dict[str, Any]] = []

    for pipeline_dir in pipeline_dirs:
        name = pipeline_dir.name
        run_dir = _latest_run_dir(pipeline_dir)
        if run_dir is None:
            logger.warning("No runs found for pipeline %s; skipping", name)
            continue
        logger.info("Pipeline %s: using run %s", name, run_dir.name)

        curve = _final_stage_curve(run_dir)
        metrics = _last_metrics(run_dir)
        if curve:
            curves[name] = curve

        if curve or metrics:
            final_curve_point = curve[-1] if curve else None
            overall = metrics["overall"] if metrics else None
            stage_dirs = sorted(p.name for p in run_dir.glob("stage_*_*") if p.is_dir())
            rows.append({
                "pipeline": name,
                "stages": "|".join(stage_dirs),
                "final_train_loss": final_curve_point["train_loss_avg"] if final_curve_point else "",
                "final_dev_f1": final_curve_point["dev_f1"] if final_curve_point else "",
                "test_precision": overall["precision"] if overall else "",
                "test_recall": overall["recall"] if overall else "",
                "test_f1": overall["f1"] if overall else "",
                "test_accuracy": overall["accuracy"] if overall else "",
            })

    if not curves:
        logger.error("No learning curves found; nothing to plot.")
        return

    plot_learning_curves_aggregate(
        curves=curves,
        output_path=output_dir / "learning_curves_all.png",
        title="Learning curves across pipelines",
    )
    _write_summary_csv(rows, output_dir / "summary.csv")
