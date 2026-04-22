"""First part of selection of corpus, where we select 15k records.

    Step 1: Filter records with no silver labels, as they are not useful for training.
    Step 2: Cap max sentences per wiki page, to ensure diversity of pages in the training set.
    Step 3: Stratified sampling, by dominant entity type (the most common entity type in the silver labels of a record).

Usage (from project root):
    python scripts/run_select_15k.py
    python scripts/run_select_15k.py --silver data/silver/hp_silver.jsonl
"""

import argparse
import json
import logging
import random
from collections import defaultdict, Counter
from pathlib import Path


import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.selection.selection import dominant_label, has_any_label


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("data/select_15k.log"),
    ],
)
logger = logging.getLogger(__name__)

ANNOTATORS = ["peter", "hanna", "zita", "anis"]

SOURCE_CAP = 50  # max sentences per wiki page

TARGETS = {
    "CHAR": 5500,
    "LOC": 2500,
    "ORG": 2500,
    "SPELL": 1500,
    "CREA": 1500,
    "ARTI": 1500,
}

TOTAL_TARGET = sum(TARGETS.values())  # 15000


# step 1
def step1_hard_filter(records: list[dict]) -> list[dict]:
    """Filter out records with no silver labels, as they are not useful for training."""
    filtered = [r for r in records if has_any_label(r)]
    dropped = len(records) - len(filtered)
    logger.info(
        f"Step 1: Filtered out {dropped}({100 * dropped / len(records):.2%}) records with no silver labels. Remaining: {len(filtered)}"
    )
    return filtered


def step2_source_cap(records: list[dict], source_cap: int = SOURCE_CAP) -> list[dict]:
    """Cap max sentences per wiki page, to ensure diversity of pages in the training set.
    Within each source, we add sentences with random number of entities, to ensure diversity of entity counts in the training set.
    """

    grouped: dict[str, list[dict]] = defaultdict(list)
    for rec in records:
        source = rec["title"]
        grouped[source].append(rec)

    capped = []
    for source, recs in grouped.items():
        random.shuffle(recs)  # ensures random selection
        capped.extend(
            recs[: min(source_cap, len(recs))]
        )  # cap to SOURCE_CAP sentences per source or all sentences if less than SOURCE_CAP

    dropped = len(records) - len(capped)
    logger.info(
        f"Step 2: Capped to {source_cap} sentences per source. Filtered out {dropped}({100 * dropped / len(records):.2%}) records. Remaining: {len(capped)}"
    )
    logger.info(f"Unique sources after capping: {len(grouped)}")

    return capped


def step3_stratified_sampling(
    records: list[dict], targets: dict[str, int], seed: int
) -> list[dict]:
    """Sample sentences stratified by dominant entity type.
    If a label has fewer candidates than target, include all and
    redistribute the shortfall to CHARACTER.
    """

    rng = random.Random(seed)  # fixed seed for reproducibility

    grouped = defaultdict(list)
    unclassified = 0

    for rec in records:
        dom = dominant_label(rec)
        if dom:
            grouped[dom].append(rec)
        else:
            unclassified += 1

    if unclassified:
        logger.warning(
            f"{unclassified} records had no dominant label and will be ignored in stratified sampling."
        )

    for group in grouped.values():
        random.shuffle(group)

    selected = []
    char_shortfall = 0

    for label, target in targets.items():
        available = grouped[label]
        take = min(len(available), target)
        shortfall = target - take
        selected.extend(available[:take])

        if shortfall > 0:
            char_shortfall += shortfall
            logger.warning(
                f"Label {label} has shortfall of {shortfall} (target {target}, available {len(available)}). Will add to CHARACTER shortfall."
            )
        else:
            logger.info(
                f"Label {label}: target {target}, available {len(available)}, taking {take}."
            )

    if char_shortfall:
        already_taken = {r["id"] for r in selected}
        char_available = [r for r in grouped["CHAR"] if r["id"] not in already_taken]

        rng.shuffle(char_available)

        if len(char_available) < char_shortfall:
            logger.warning(
                f"CHAR label has shortfall of {char_shortfall} but only {len(char_available)} available. Will take all available."
            )
            char_shortfall = len(char_available)

        selected.extend(char_available[:char_shortfall])
        logger.info(
            f"Added {char_shortfall} to CHARACTER from shortfall redistribution. Total CHARACTER selected: {len([r for r in selected if dominant_label(r) == 'CHAR'])}."
        )

    rng.shuffle(selected)
    logger.info(
        f"Step 3: Stratified sampling by dominant label. Final selected count: {len(selected)}. Distribution: { {label: len([r for r in selected if dominant_label(r) == label]) for label in TARGETS.keys()} }"
    )
    if len(selected) < TOTAL_TARGET:
        logger.warning(
            f"Total selected {len(selected)} is less than total target {TOTAL_TARGET}. Consider adjusting targets or checking availability."
        )
    return selected


def log_stats(records: list[dict]) -> None:
    """Log statistics about the selected records."""
    type_dist = Counter(dominant_label(r) for r in records)
    entity_dist = Counter(r["entity_count"] for r in records)

    logger.info("=" * 60)
    logger.info("FINAL COMPOSITION")
    logger.info("=" * 60)
    logger.info(f"Total selected records: {len(records)}")

    logger.info("\nDominant type distribution:")
    for label in TARGETS.keys():
        count = type_dist.get(label, 0)
        logger.info(f"{label}: {count} records percentage: {count / len(records):.1%}")

    logger.info("\nEntity count distribution:")
    for n in sorted(entity_dist.keys()):
        count = entity_dist[n]
        logger.info(
            f"{n} entities: {count} records percentage: {count / len(records):.1%}"
        )

    logger.info(f"\nUnique sources: {len(set(r['title'] for r in records))}")

    logger.info("=" * 60)


# Main:


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Stratified Corpus Selection")
    p.add_argument("--silver", default="data/silver/hp_silver.jsonl")
    p.add_argument("--output", default="data/selected/hp_15k.jsonl")
    p.add_argument("--source-cap", type=int, default=SOURCE_CAP)
    p.add_argument("--seed", type=int, default=42)
    return p.parse_args()


def main():
    args = parse_args()

    silver_path = Path(args.silver)
    if not silver_path.exists():
        logger.error(f"Silver file not found at {silver_path}")
        return

    logger.info(f"Loading silver records from {silver_path}")
    records = []
    with open(silver_path, "r", encoding="utf-8") as f:
        for line in f:
            records.append(json.loads(line))
    logger.info(f"Loaded {len(records)} silver records.")

    # 3 steps
    records = step1_hard_filter(records)
    records = step2_source_cap(records, args.source_cap)
    records = step3_stratified_sampling(records, TARGETS, args.seed)

    log_stats(records)

    # Write output

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec) + "\n")
    logger.info(f"Wrote {len(records)} selected records to {output_path}")


if __name__ == "__main__":
    main()
