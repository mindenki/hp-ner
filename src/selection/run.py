"""Selection orchestration: the 15k stratified sample + the 1,250 gold pool.

Two entry points, each called from ``scripts/prepare_annotation.py`` as a
one-liner:

  * ``select_15k_entrypoint(input_path, output_path)``        — stratified 15k sample.
  * ``select_gold_pool_entrypoint(input_path, output_dir)``   — 4-bucket gold pool + overlap
    + per-annotator unique splits.

The low-level building blocks (``dominant_label``, ``has_conflict``, bucket
predicates, the 15k filter/cap/stratify steps) live in ``selection.py``.
"""
import json
import logging
import random
from pathlib import Path

from src.selection.selection import (
    cap_per_source,
    distinct_entity_types,
    filter_unlabeled,
    has_conflict,
    is_high_confidence,
    split_unique_per_annotator,
    stratified_sample,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# select_15k_entrypoint
# ---------------------------------------------------------------------------

def select_15k_entrypoint(input_path: Path, output_path: Path, *, seed: int = 42) -> None:
    """End-to-end 15k stratified sample: filter -> cap -> stratify -> write JSONL."""
    records = [
        json.loads(line)
        for line in input_path.read_text(encoding="utf-8").splitlines()
        if line
    ]
    logger.info("select_15k_entrypoint: loaded %d silver records from %s", len(records), input_path)
    records = filter_unlabeled(records)
    records = cap_per_source(records, seed=seed)
    records = stratified_sample(records, seed=seed)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec) + "\n")
    logger.info("select_15k_entrypoint: wrote %d records to %s", len(records), output_path)


# ---------------------------------------------------------------------------
# select_gold_pool_entrypoint
# ---------------------------------------------------------------------------

ANNOTATORS: list[str] = ["peter", "hanna", "zita", "anis"]
RARE_LABELS: set[str] = {"SPELL", "CREA", "ARTI"}
BUCKET_TARGETS: dict[str, int] = {
    "A_high_confidence": 125,
    "B_rare_types": 375,
    "C_conflict": 375,
    "D_multi_type": 375,
}
OVERLAP_RATE: float = 0.15


def _select_buckets(
    records: list[dict],
    targets: dict[str, int],
    overlap_count: int,
    seed: int,
) -> dict[str, list[dict]]:
    """Fill buckets in order D -> C -> B -> A so the rarest/hardest go first."""
    rng = random.Random(seed)
    used: set = set()

    def _sample(pool: list[dict], n: int) -> list[dict]:
        available = [r for r in pool if r["id"] not in used]
        rng.shuffle(available)
        chosen = available[:n]
        used.update(r["id"] for r in chosen)
        return chosen

    d_pool = [r for r in records if len(distinct_entity_types(r)) > 2]
    bucket_d = _sample(d_pool, targets["D_multi_type"])
    logger.info("Bucket D (multi-type): pool=%d selected=%d", len(d_pool), len(bucket_d))

    c_pool = [r for r in records if has_conflict(r)]
    bucket_c = _sample(c_pool, targets["C_conflict"])
    logger.info("Bucket C (conflict): pool=%d selected=%d", len(c_pool), len(bucket_c))

    b_pool = [
        r
        for r in records
        if distinct_entity_types(r) & RARE_LABELS
    ]
    bucket_b = _sample(b_pool, targets["B_rare_types"])
    logger.info("Bucket B (rare): pool=%d selected=%d", len(b_pool), len(bucket_b))

    a_pool = [r for r in records if is_high_confidence(r)]
    bucket_a = _sample(a_pool, targets["A_high_confidence"])
    logger.info("Bucket A (high-conf): pool=%d selected=%d", len(a_pool), len(bucket_a))

    bcd = bucket_b + bucket_c + bucket_d
    rng.shuffle(bcd)
    overlap = bcd[:overlap_count]
    logger.info("Overlap set: target=%d selected=%d", overlap_count, len(overlap))

    return {
        "A_high_confidence": bucket_a,
        "B_rare_types": bucket_b,
        "C_conflict": bucket_c,
        "D_multi_type": bucket_d,
        "overlap": overlap,
    }


def _write_jsonl(records: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    logger.info("wrote %d records to %s", len(records), path)


def select_gold_pool_entrypoint(input_path: Path, output_dir: Path, *, seed: int = 42) -> None:
    """Select ~1,250 sentences for human annotation + overlap + per-annotator splits.

    Output layout (under ``output_dir``):
        overlap.jsonl                      — shared across annotators (IAA)
        {peter,hanna,zita,anis}_unique.jsonl — per-annotator unique sentences
        remaining_silver.jsonl             — everything NOT picked into gold
    """
    records = [
        json.loads(line)
        for line in input_path.read_text(encoding="utf-8").splitlines()
        if line
    ]
    logger.info("select_gold_pool_entrypoint: loaded %d records from %s", len(records), input_path)

    total_gold = sum(BUCKET_TARGETS.values())
    overlap_count = round(total_gold * OVERLAP_RATE)
    buckets = _select_buckets(records, BUCKET_TARGETS, overlap_count, seed)

    gold_ids = {
        r["id"] for name, recs in buckets.items() if name != "overlap" for r in recs
    }
    remaining_silver = [r for r in records if r["id"] not in gold_ids]
    logger.info("Remaining silver pool size: %d", len(remaining_silver))

    overlap = buckets.pop("overlap")
    overlap_ids = {r["id"] for r in overlap}
    all_unique = [
        r for recs in buckets.values() for r in recs if r["id"] not in overlap_ids
    ]
    annotator_splits = split_unique_per_annotator(
        all_unique, ANNOTATORS, random.Random(seed)
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    _write_jsonl(overlap, output_dir / "overlap.jsonl")
    for annotator, recs in annotator_splits.items():
        _write_jsonl(recs, output_dir / f"{annotator}_unique.jsonl")
    _write_jsonl(remaining_silver, output_dir / "remaining_silver.jsonl")
    logger.info("select_gold_pool_entrypoint: done — outputs in %s", output_dir)
