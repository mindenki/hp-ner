"""Orchestrator 2/3: turn Doccano-annotated JSONL into gold/silver IOB2.

Steps:
    export_from_doccano - pull JSONL exports from running Doccano
    compute_iaa         - pairwise Cohen kappa per token
    merge_gold          - majority vote on overlap; interactive prompt on ties
                          (writes data/iaa/overrides.jsonl)
    write_iob2          - apply overrides + write
                          data/selected/silver/silver.iob2 and gold/gold.iob2

Step selection:
    --only-step STEP   repeatable; run only the listed step(s). Default = all.
"""
import argparse
import logging
import sys
from pathlib import Path

from src.common.logging import setup_logging
from src.iaa.agreement import compute_iaa_entrypoint

logger = logging.getLogger(__name__)

ANNOTATORS = ["peter", "hanna", "zita", "anis"]
STEPS = ["export_from_doccano", "compute_iaa", "merge_gold", "write_iob2"]


def _prompt_resolution(text: str, candidates: list[dict]) -> list[dict]:
    """Interactive picker for unresolved spans. UI concern — stays in the orchestrator.

    ``candidates`` items look like ``{"span": (s, e, label), "count": n}``.
    """
    print(f"\nConflict on: {text!r}")
    for i, c in enumerate(candidates, start=1):
        s, e, label = c["span"]
        print(f"  [{i}] {text[s:e]!r}  ({label})  votes={c['count']}")
    print(f"  [{len(candidates) + 1}] none of the above")
    while True:
        choice = input("Pick number (or 'q' to quit): ").strip()
        if choice.lower() == "q":
            sys.exit(130)
        try:
            idx = int(choice)
        except ValueError:
            continue
        if 1 <= idx <= len(candidates):
            s, e, label = candidates[idx - 1]["span"]
            return [{"start": s, "end": e, "label": label}]
        if idx == len(candidates) + 1:
            return []


def _step_export(args) -> None:
    if args.skip_export:
        logger.info("export_from_doccano: --skip-export set; assuming data/annotated/ is present")
        return
    import requests
    from src.annotation.run import export_from_doccano_entrypoint
    try:
        export_from_doccano_entrypoint(Path("data/annotated"))
    except requests.ConnectionError:
        logger.error(
            "export_from_doccano: cannot reach Doccano at localhost:8000. "
            "Start it (`cd doccano && docker compose up -d`) or pass --skip-export "
            "to use existing data/annotated/ files."
        )
        sys.exit(1)


def _step_compute_iaa(args) -> None:
    overlap_paths = {
        name: Path(f"data/annotated/{name}_overlap.jsonl") for name in ANNOTATORS
    }
    missing = [p for p in overlap_paths.values() if not p.exists()]
    if missing:
        logger.error("compute_iaa: missing exports: %s", missing)
        sys.exit(1)
    report = compute_iaa_entrypoint(
        overlap_paths,
        Path("data/iaa/agreement.json"),
        threshold=args.iaa_threshold,
    )
    if not report["passes_threshold"] and not args.allow_low_agreement:
        logger.error(
            "Mean pairwise kappa %.3f < threshold %.2f; rerun with --allow-low-agreement to override",
            report["mean_pairwise_cohen_kappa"],
            args.iaa_threshold,
        )
        sys.exit(2)


def _step_merge(args) -> None:
    """Resolve conflicts interactively and persist overrides.jsonl. No file output."""
    from src.annotation.run import merge_gold_entrypoint
    on_conflict = None if args.non_interactive else _prompt_resolution
    merge_gold_entrypoint(
        annotated_dir=Path("data/annotated"),
        overrides_path=Path("data/iaa/overrides.jsonl"),
        on_conflict=on_conflict,
    )


def _step_write_iob2(args) -> None:
    """Apply overrides and write gold + silver IOB2.

    Re-runs the merge non-interactively (reading the overrides written by
    _step_merge) so this step is independently invocable.
    """
    from src.annotation.run import merge_gold_entrypoint, write_iob2_entrypoint
    merged = merge_gold_entrypoint(
        annotated_dir=Path("data/annotated"),
        overrides_path=Path("data/iaa/overrides.jsonl"),
        on_conflict=None,
    )
    write_iob2_entrypoint(
        merged,
        silver_jsonl=Path("data/silver/hp_silver.jsonl"),
        gold_iob2_out=Path("data/selected/gold/gold.iob2"),
        silver_iob2_out=Path("data/selected/silver/silver.iob2"),
    )


_STEP_FUNCS = {
    "export_from_doccano": _step_export,
    "compute_iaa": _step_compute_iaa,
    "merge_gold": _step_merge,
    "write_iob2": _step_write_iob2,
}


def _select_steps(args) -> list[str]:
    if not args.only_step:
        return STEPS
    unknown = [s for s in args.only_step if s not in STEPS]
    if unknown:
        raise SystemExit(f"--only-step unknown: {unknown!r}; valid: {STEPS}")
    return [s for s in STEPS if s in set(args.only_step)]


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--only-step", action="append", default=[], choices=STEPS,
                   help="Run only the listed step(s); repeatable. Default: all steps.")
    p.add_argument("--skip-export", action="store_true")
    p.add_argument("--iaa-threshold", type=float, default=0.7)
    p.add_argument("--allow-low-agreement", action="store_true")
    p.add_argument("--non-interactive", action="store_true")
    return p.parse_args()


def main() -> None:
    setup_logging("finalize_gold")
    args = _parse_args()
    for step in _select_steps(args):
        logger.info("=== step: %s ===", step)
        try:
            _STEP_FUNCS[step](args)
        except Exception:
            logger.exception("step %s failed", step)
            sys.exit(1)
    logger.info("finalize_gold complete")


if __name__ == "__main__":
    main()
