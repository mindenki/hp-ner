"""Orchestrator 1/3: prepare HP data for human annotation.

Steps (in declaration order):
    train_ewt        — fine-tune DeBERTaV3 on EWT NER (skipped if checkpoint exists)
    scrape           — crawl the HP Fandom wiki                (--force-scrape to redo)
    clean            — sentence-split + normalise              (skipped if data/filtered/ exists)
    build_dict       — build entity dictionary from wiki       (skipped if dict files exist)
    silver_label     — apply BERT + dictionary tagging         (skipped if silver jsonl exists)
    select_15k       — stratified sample of 15 000 sentences   (skipped if output exists)
    select_gold_pool — pick 1 250 sentences across 4 buckets   (skipped if output exists)
    setup_doccano    — create projects + import JSONLs         (--skip-doccano to omit)

Step selection:
    --only-step STEP   repeatable; run only the listed step(s). Default = all.

Usage:
    uv run prepare-annotation
    uv run prepare-annotation --only-step silver_label
    uv run prepare-annotation --only-step clean --only-step silver_label
    uv run prepare-annotation --force-scrape --force-silver
"""
import argparse
import logging
import sys
from pathlib import Path

import yaml

from src.common.logging import setup_logging

logger = logging.getLogger(__name__)

STEPS = [
    "train_ewt",
    "scrape",
    "clean",
    "build_dict",
    "silver_label",
    "select_15k",
    "select_gold_pool",
    "setup_doccano",
]


# ---------------------------------------------------------------------------
# Step implementations
# ---------------------------------------------------------------------------


def _step_train_ewt(args) -> None:
    existing = sorted(Path("outputs/baseline").glob("run_*/best_model"))
    if existing and not args.force_ewt:
        logger.info("train_ewt: existing checkpoint found at %s — skipping", existing[-1])
        return
    cfg = yaml.safe_load(Path(args.config).read_text(encoding="utf-8"))
    from src.baseline.train import train_ewt_entrypoint
    train_ewt_entrypoint(cfg)


def _step_scrape(args) -> None:
    out = Path("data/raw/wiki_data.jsonl")
    if out.exists() and not args.force_scrape:
        logger.info("scrape: %s already exists — skipping", out)
        return
    from src.scraping.run import scrape_entrypoint
    scrape_entrypoint(out)


def _step_clean(args) -> None:
    filtered = Path("data/filtered/wiki_data_filtered.jsonl")
    if filtered.exists() and not args.force_clean:
        logger.info("clean: %s already exists — skipping", filtered)
        return
    from src.preprocessing.run import clean_entrypoint
    clean_entrypoint(
        raw_path=Path("data/raw/wiki_data.jsonl"),
        cleaned_path=Path("data/cleaned/wiki_data_clean.jsonl"),
        filtered_path=filtered,
    )


def _step_build_dict(args) -> None:
    dict_dir = Path("data/dictionaries/txts")
    if dict_dir.exists() and any(dict_dir.iterdir()) and not args.force_dict:
        logger.info("build_dict: %s already populated — skipping", dict_dir)
        return
    from src.dict_builder.run import build_dict_entrypoint
    build_dict_entrypoint(Path("data/dictionaries"))


def _step_silver_label(args) -> None:
    out = Path("data/silver/hp_silver.jsonl")
    if out.exists() and not args.force_silver:
        logger.info("silver_label: %s already exists — skipping", out)
        return
    input_path = Path("data/filtered/wiki_data_filtered.jsonl")
    if not input_path.exists():
        logger.error("silver_label: input file not found at %s", input_path)
        sys.exit(1)
    from src.silver_labeling.run import silver_label_entrypoint
    silver_label_entrypoint(
        input_path=input_path,
        output_path=out,
        dictionary_dir=Path("data/dictionaries/txts"),
        ewt_run=args.ewt_run,
    )


def _step_select_15k(args) -> None:
    out = Path("data/selected/silver/hp_15k.jsonl")
    if out.exists() and not args.force_select_15k:
        logger.info("select_15k: %s already exists — skipping", out)
        return
    silver_path = Path("data/silver/hp_silver.jsonl")
    if not silver_path.exists():
        logger.error("select_15k: silver file not found at %s", silver_path)
        sys.exit(1)
    from src.selection.run import select_15k_entrypoint
    select_15k_entrypoint(input_path=silver_path, output_path=out, seed=42)


def _step_select_gold_pool(args) -> None:
    out = Path("data/selected/gold_pool")
    if out.exists() and any(out.iterdir()) and not args.force_gold_pool:
        logger.info("select_gold_pool: %s already populated — skipping", out)
        return
    input_path = Path("data/selected/silver/hp_15k.jsonl")
    if not input_path.exists():
        logger.error("select_gold_pool: input not found at %s", input_path)
        sys.exit(1)
    from src.selection.run import select_gold_pool_entrypoint
    select_gold_pool_entrypoint(input_path=input_path, output_dir=out, seed=42)


def _step_setup_doccano(args) -> None:
    if args.skip_doccano:
        logger.info("setup_doccano: --skip-doccano set; not contacting Doccano")
        return
    from src.annotation.run import setup_doccano_entrypoint
    setup_doccano_entrypoint(Path("data/selected/gold_pool"))


_STEP_FUNCS = {
    "train_ewt": _step_train_ewt,
    "scrape": _step_scrape,
    "clean": _step_clean,
    "build_dict": _step_build_dict,
    "silver_label": _step_silver_label,
    "select_15k": _step_select_15k,
    "select_gold_pool": _step_select_gold_pool,
    "setup_doccano": _step_setup_doccano,
}


def _select_steps(args) -> list:
    if not args.only_step:
        return STEPS
    unknown = [s for s in args.only_step if s not in STEPS]
    if unknown:
        raise SystemExit(f"--only-step unknown: {unknown!r}; valid: {STEPS}")
    return [s for s in STEPS if s in set(args.only_step)]


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--config", default="configs/baseline.yaml")
    p.add_argument(
        "--only-step",
        action="append",
        default=[],
        choices=STEPS,
        help="Run only the listed step(s); repeatable. Default: all steps.",
    )
    p.add_argument("--force-ewt", action="store_true")
    p.add_argument("--force-scrape", action="store_true")
    p.add_argument("--force-clean", action="store_true")
    p.add_argument("--force-dict", action="store_true")
    p.add_argument("--force-silver", action="store_true")
    p.add_argument("--force-select-15k", action="store_true")
    p.add_argument("--force-gold-pool", action="store_true")
    p.add_argument("--skip-doccano", action="store_true")
    p.add_argument(
        "--ewt-run",
        default=None,
        help="EWT run folder name for BertTagger. Defaults to LATEST_RUN.txt.",
    )
    return p.parse_args()


def main() -> None:
    setup_logging("prepare_annotation")
    args = _parse_args()
    for step in _select_steps(args):
        logger.info("=== step: %s ===", step)
        try:
            _STEP_FUNCS[step](args)
        except Exception:
            logger.exception("step %s failed", step)
            sys.exit(1)
    logger.info("prepare_annotation complete")


if __name__ == "__main__":
    main()
