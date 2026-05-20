"""Cross-pipeline aggregate plot + summary CSV.

After ``run_pipelines`` has populated ``outputs/pipelines/<name>/run_*/``, this script:

1. Picks the most recent run for each pipeline (LATEST_RUN.txt or newest run_* dir).
2. Reads the final stage's learning_curve.json and the last metrics.jsonl line.
3. Writes:
     - outputs/aggregate/learning_curves_all.png
     - outputs/aggregate/summary.csv

Usage:
    uv run aggregate-plots
    uv run aggregate-plots --runs-root outputs/pipelines --output-dir outputs/aggregate
"""
from __future__ import annotations

import argparse
import csv
import json
import logging
import sys
from pathlib import Path
from typing import Any

from baseline.src.plots import plot_learning_curves_aggregate

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

logger = logging.getLogger(__name__)


def _setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[logging.StreamHandler(sys.stdout)],
    )


def _latest_run_dir(pipeline_dir: Path) -> Path | None:
    """Resolve the most recent run for a pipeline."""
    pointer = pipeline_dir / "LATEST_RUN.txt"
    if pointer.exists():
        run = (pipeline_dir / pointer.read_text(encoding="utf-8").strip())
        if run.exists():
            return run
        logger.warning(f"LATEST_RUN.txt for {pipeline_dir.name} points to missing folder: {run}")
    candidates = sorted(
        (p for p in pipeline_dir.glob("run_*") if p.is_dir()),
        key=lambda p: p.name,
        reverse=True,
    )
    return candidates[0] if candidates else None


def _final_stage_curve(run_dir: Path) -> list[dict] | None:
    """Find the highest-numbered ``stage_*_*`` subdir and load its learning_curve.json."""
    stages = sorted(
        (p for p in run_dir.glob("stage_*_*") if p.is_dir()),
        key=lambda p: p.name,
    )
    if not stages:
        logger.warning(f"No stage subdirs found under {run_dir}")
        return None
    curve_path = stages[-1] / "learning_curve.json"
    if not curve_path.exists():
        logger.warning(f"Missing learning_curve.json at {curve_path}")
        return None
    return json.loads(curve_path.read_text(encoding="utf-8"))


def _last_metrics(run_dir: Path) -> dict[str, Any] | None:
    """Read the last JSON line from metrics.jsonl."""
    path = run_dir / "metrics.jsonl"
    if not path.exists():
        logger.warning(f"Missing metrics.jsonl at {path}")
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
        "pipeline",
        "stages",
        "final_train_loss",
        "final_dev_f1",
        "test_precision",
        "test_recall",
        "test_f1",
        "test_accuracy",
    ]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in fieldnames})
    logger.info(f"Wrote aggregate summary to {output_path}")


def main() -> None:
    _setup_logging()
    parser = argparse.ArgumentParser(description="Cross-pipeline aggregate plot + summary CSV.")
    parser.add_argument(
        "--runs-root",
        default=str(_PROJECT_ROOT / "outputs" / "pipelines"),
        help="Root containing per-pipeline subdirectories.",
    )
    parser.add_argument(
        "--output-dir",
        default=str(_PROJECT_ROOT / "outputs" / "aggregate"),
        help="Where to write learning_curves_all.png and summary.csv.",
    )
    args = parser.parse_args()

    runs_root = Path(args.runs_root)
    output_dir = Path(args.output_dir)

    if not runs_root.exists():
        logger.error(f"runs-root does not exist: {runs_root}")
        sys.exit(1)

    pipeline_dirs = sorted(p for p in runs_root.iterdir() if p.is_dir())
    if not pipeline_dirs:
        logger.error(f"No pipeline directories under {runs_root}")
        sys.exit(1)

    curves: dict[str, list[dict]] = {}
    rows: list[dict[str, Any]] = []

    for pipeline_dir in pipeline_dirs:
        name = pipeline_dir.name
        run_dir = _latest_run_dir(pipeline_dir)
        if run_dir is None:
            logger.warning(f"No runs found for pipeline {name}; skipping")
            continue
        logger.info(f"Pipeline {name}: using run {run_dir.name}")

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
        logger.error("No learning curves found across pipelines; nothing to plot.")
        sys.exit(1)

    plot_learning_curves_aggregate(
        curves=curves,
        output_path=output_dir / "learning_curves_all.png",
        title="Learning curves across pipelines",
    )
    _write_summary_csv(rows, output_dir / "summary.csv")


if __name__ == "__main__":
    main()
