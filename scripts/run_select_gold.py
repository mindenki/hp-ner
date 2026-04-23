"""Gold Annotation Pool Selection
Selects ~1,250 sentences from the 15k corpus for human annotation
using a 4-bucket strategy, plus an overlap set for IAA.

Buckets:
    A — High-confidence silver labels(meaning has no conflict and at least one label agreement)  (375 sentences)
    B — Rare entity types (SPELL, CREA, ARTI) being dominant label         (375 sentences)
    C — BERT/dict conflict              (375 sentences)
    D — Multi-type sentences            (125 sentences)
    Overlap set (15% of total, ~188)    drawn from B + C + D

Usage (from project root):
    python scripts/run_select_gold.py
    python scripts/run_select_gold.py --input data/selected/hp_15k.jsonl

"""

import argparse
import json
import logging
import random
from pathlib import Path

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.selection.selection import (
    dominant_label,
    has_conflict,
    is_high_confidence,
    distinct_entity_types,
    split_unique_per_annotator,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("data/select_gold.log"),
    ],
)
logger = logging.getLogger(__name__)

ANNOTATORS = ["peter", "hanna", "zita", "anis"]

RARE_LABELS = {"SPELL", "CREA", "ARTI"}

BUCKET_TARGETS: dict[str, int] = {
    "A_high_confidence": 125,
    "B_rare_types": 375,
    "C_conflict": 375,
    "D_multi_type": 375,
}
TOTAL_GOLD = sum(BUCKET_TARGETS.values())  # 1,250
OVERLAP_RATE = 0.15  # overlap for IAA, drawn from B + C + D
OVERLAP_COUNT = round(TOTAL_GOLD * OVERLAP_RATE)  # 188 sentences


# bucket selection


def select_buckets(
    records: list[dict], targets: dict[str, int], overlap_count: int, seed: int
) -> dict[str, list[dict]]:
    """
    FILLS the buckets in order from D->C->B->A, so hardest/rarest first, so the
    the informative sentences are not "used up" by the easier buckets. The overlap set is drawn from B + C + D,
    to ensure it contains informative sentences. We keep track of used_ids to ensure no sentence is selected more than once, except for the overlap set.
    """
    rng = random.Random(seed)
    used_ids = set()

    def _sample(pool: list[dict], n: int) -> list[dict]:
        available = [r for r in pool if r["id"] not in used_ids]
        rng.shuffle(available)
        chosen = available[:n]
        used_ids.update(r["id"] for r in chosen)
        return chosen

    # Bucket D - multi-type (>2 distinct entity types)
    d_pool = [r for r in records if len(distinct_entity_types(r)) > 2]
    bucket_d = _sample(d_pool, targets["D_multi_type"])
    logger.info(f"Bucket D (multi-type): pool={len(d_pool)} selected={len(bucket_d)}")

    if len(bucket_d) < targets["D_multi_type"]:
        logger.warning(
            f"Bucket D underfilled: needed {targets['D_multi_type']} but only found {len(bucket_d)}"
        )

    # Bucket C - BERT/dict conflict
    c_pool = [r for r in records if has_conflict(r)]
    bucket_c = _sample(c_pool, targets["C_conflict"])
    logger.info(f"Bucket C (conflict): pool={len(c_pool)} selected={len(bucket_c)}")

    if len(bucket_c) < targets["C_conflict"]:
        logger.warning(
            f"Bucket C underfilled: needed {targets['C_conflict']} but only found {len(bucket_c)}"
        )

    # Bucket B - rare entity types (SPELL, CREA, ARTI)
    b_pool = [r for r in records if dominant_label(r) in RARE_LABELS]
    bucket_b = _sample(b_pool, targets["B_rare_types"])
    logger.info(f"Bucket B (rare types): pool={len(b_pool)} selected={len(bucket_b)}")

    if len(bucket_b) < targets["B_rare_types"]:
        logger.warning(
            f"Bucket B underfilled: needed {targets['B_rare_types']} but only found {len(bucket_b)}"
        )

    # Bucket A - high-confidence silver labels (no conflict and at least one agreement)
    a_pool = [r for r in records if is_high_confidence(r)]
    bucket_a = _sample(a_pool, targets["A_high_confidence"])
    logger.info(
        f"Bucket A (high-confidence): pool={len(a_pool)} selected={len(bucket_a)}"
    )

    if len(bucket_a) < targets["A_high_confidence"]:
        logger.warning(
            f"Bucket A underfilled: needed {targets['A_high_confidence']} but only found {len(bucket_a)}"
        )

    # Overlap set drawn from B + C + D
    bcd_combined = bucket_b + bucket_c + bucket_d
    rng.shuffle(bcd_combined)
    overlap = bcd_combined[:overlap_count]
    logger.info(f"Overlap set: target={overlap_count} selected={len(overlap)}")

    return {
        "A_high_confidence": bucket_a,
        "B_rare_types": bucket_b,
        "C_conflict": bucket_c,
        "D_multi_type": bucket_d,
        "overlap": overlap,
    }


# stats logging


def log_stats(gold: dict[str, list[dict]]) -> None:
    """Log statistics about the selected gold pool and buckets."""

    logger.info("=" * 60)
    logger.info("GOLD ANNOTATION POOL SUMMARY")
    logger.info("=" * 60)

    all_gold_ids = set()

    for name, bucket in gold.items():
        if name == "overlap":
            continue
        all_gold_ids.update(r["id"] for r in bucket)
        logger.info(f"Bucket {name}: {len(bucket)} sentences")

    logger.info(
        f"Total overlap sentences (in multiple buckets): {len(gold['overlap'])}"
    )
    logger.info(
        f"Total unique sentences in gold pool (excluding overlap): {len(all_gold_ids)}"
    )

    # per-annotator
    overlap_count = len(gold["overlap"])
    unique_count = len(all_gold_ids) - overlap_count
    unique_per_annotator = unique_count // 4
    logger.info("\nPer-annotator workload:")
    logger.info(f"Unique sentences per annotator: {unique_per_annotator}")
    logger.info(f"Overlap sentences per annotator: {overlap_count}")
    logger.info(
        f"Total sentences per annotator: {unique_per_annotator + overlap_count}"
    )

    logger.info("=" * 60)


def write_jsonl(records: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    logger.info(f"Wrote {len(records)} records to {path}")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="S6b — Gold Annotation Pool Selection")
    p.add_argument("--input", default="data/selected/hp_15k.jsonl")
    p.add_argument("--output-dir", default="data/selected/gold")
    p.add_argument("--seed", type=int, default=42)
    return p.parse_args()


def main():
    args = parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        logger.error(f"Input file not found at {input_path}")
        return

    logger.info(f"Loading records from {input_path}")
    records = []

    with open(input_path, "r", encoding="utf-8") as f:
        for line in f:
            records.append(json.loads(line))
    logger.info(f"Loaded {len(records)} records.")

    # select gold buckets
    gold = select_buckets(records, BUCKET_TARGETS, OVERLAP_COUNT, args.seed)
    buckets = {k: v for k, v in gold.items() if k != "overlap"}
    overlap = gold["overlap"]

    overlap_ids = {r["id"] for r in overlap}
    all_unique = [
        r for recs in buckets.values() for r in recs if r["id"] not in overlap_ids
    ]
    # dedup in case of any accidental overlaps between buckets (should be rare since we track used_ids, but just in case)
    # seen = set()
    # all_unique_deduped: list[dict] = []
    # for r in all_unique:
    #     if r["id"] not in seen:
    #         seen.add(r["id"])
    #         all_unique_deduped.append(r)

    rng = random.Random(args.seed)

    annotator_splits = split_unique_per_annotator(all_unique, ANNOTATORS, rng)

    output_dir = Path(args.output_dir)
    logger.info(f"Writing output to {output_dir}")

    write_jsonl(overlap, output_dir / "overlap.jsonl")
    for annotator, recs in annotator_splits.items():
        write_jsonl(recs, output_dir / f"{annotator}_unique.jsonl")

    log_stats(gold)
    logger.info(
        "Gold selection completed. Files ready for import with setup_doccano_project.py"
    )


if __name__ == "__main__":
    main()
