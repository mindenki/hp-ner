"""Orchestrator 3/3: split gold, train all HP pipelines, evaluate, plot.

Steps:
    split_gold        - stratified 80/10/10 of gold.iob2
    run_pipelines     - six pipelines defined in configs/pipelines.yaml
    aggregate_plots   - cross-pipeline learning-curve PNG + summary CSV
    gpt4o_reference   - optional GPT-4o predictions (needs --with-llm-reference)

Step selection:
    --only-step STEP         repeatable; run only the listed step(s). Default = all.

Pipeline filtering (inside the run_pipelines step):
    --only-pipeline NAME     repeatable; default = all six
    --skip-pipeline NAME     repeatable
"""
import argparse
import logging
import os
from pathlib import Path

import yaml

from src.common.logging import setup_logging

logger = logging.getLogger(__name__)
STEPS = ["split_gold", "run_pipelines", "aggregate_plots", "gpt4o_reference"]


def _step_split_gold(args) -> None:
    if Path("data/selected/gold/train.iob2").exists() and not args.force_split:
        logger.info("split_gold: train/dev/test exist — skipping")
        return
    from src.modeling.splitter import SplitRatios, split_gold_entrypoint
    split_gold_entrypoint(
        gold_path=Path("data/selected/gold/gold.iob2"),
        output_dir=Path("data/selected/gold"),
        ratios=SplitRatios(train=0.8, dev=0.1, test=0.1),
        seed=42,
    )


def _step_run_pipelines(args) -> None:
    from src.modeling.run import run_pipelines_entrypoint
    run_pipelines_entrypoint(
        Path(args.pipelines_config),
        only=args.only_pipeline,
        skip=args.skip_pipeline,
    )


def _step_aggregate(args) -> None:
    from src.modeling.run import aggregate_plots_entrypoint
    cfg = yaml.safe_load(Path(args.pipelines_config).read_text(encoding="utf-8"))
    runs_root = Path(cfg["paths"]["output_root"])
    aggregate_plots_entrypoint(runs_root, runs_root.parent / "aggregate")


def _step_gpt4o(args) -> None:
    if not args.with_llm_reference:
        logger.info("gpt4o_reference: --with-llm-reference not set; skipping")
        return
    if not os.getenv("OPENAI_API_KEY"):
        logger.warning("OPENAI_API_KEY not set; skipping gpt4o_reference")
        return
    from llm_reference.predict import gpt4o_reference_entrypoint
    cfg = yaml.safe_load(Path(args.pipelines_config).read_text(encoding="utf-8"))
    gpt4o_reference_entrypoint(
        Path(cfg["paths"]["gold_test"]),
        Path("outputs/gpt4o/predictions/test.iob2"),
    )


_STEP_FUNCS = {
    "split_gold": _step_split_gold,
    "run_pipelines": _step_run_pipelines,
    "aggregate_plots": _step_aggregate,
    "gpt4o_reference": _step_gpt4o,
}


def _select_steps(args) -> list[str]:
    if not args.only_step:
        return STEPS
    unknown = [s for s in args.only_step if s not in STEPS]
    if unknown:
        raise SystemExit(f"--only-step unknown: {unknown!r}; valid: {STEPS}")
    return [s for s in STEPS if s in set(args.only_step)]


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--pipelines-config", default="configs/pipelines.yaml")
    p.add_argument("--only-step", action="append", default=[], choices=STEPS,
                   help="Run only the listed step(s); repeatable. Default: all steps.")
    p.add_argument("--only-pipeline", action="append", default=[],
                   help="Filter pipelines inside the run_pipelines step. Repeatable.")
    p.add_argument("--skip-pipeline", action="append", default=[])
    p.add_argument("--with-llm-reference", action="store_true")
    p.add_argument("--force-split", action="store_true")
    return p.parse_args()


def main() -> None:
    setup_logging("train_and_evaluate")
    args = _parse_args()
    for step in _select_steps(args):
        logger.info("=== step: %s ===", step)
        _STEP_FUNCS[step](args)
    logger.info("train_and_evaluate complete")


if __name__ == "__main__":
    main()
