"""Helper functions for corpus selection.

Two layers:
  * Record-level predicates (``dominant_label``, ``has_conflict``, ...).
  * The 3-step stratified sampler used by `scripts/prepare_annotation.py`'s
    `select_15k` step: ``filter_unlabeled`` -> ``cap_per_source`` ->
    ``stratified_sample``.
"""

import logging
import random
from collections import Counter, defaultdict

logger = logging.getLogger(__name__)


# Defaults used by the 15k stratified sampler. Orchestrators may override.
SOURCE_CAP: int = 20
TARGETS: dict[str, int] = {
    "CHAR": 5500,
    "LOC": 2500,
    "ORG": 2500,
    "SPELL": 1500,
    "CREA": 1500,
    "ARTI": 1500,
}
TOTAL_TARGET: int = sum(TARGETS.values())


def dominant_label(record: dict) -> str | None:
    """Return the most common label in the record's silver tags, in case of ties,
    it preferes rarer labels (ARTI > CREA > SPELL > ORG > LOC > CHAR)
    """

    priority = ["ARTI", "CREA", "SPELL", "ORG", "LOC", "CHAR"]

    counts = Counter()
    for tag in record["silver_labels"]:
        if tag != "O":
            if tag.split("-")[0] == "B":
                label = tag.split("-")[1]
                counts[label] += 1
    if not counts:
        return None
    max_count = max(counts.values())
    candidates = [label for label, count in counts.items() if count == max_count]
    candidates.sort(key=lambda l: priority.index(l))

    return candidates[0] or None


def has_conflict(record: dict) -> bool:
    """Returns True if the record has any BERT/dict conflicts in its silver labels."""
    return record["number_of_conflicts"] > 0


def has_any_label(record: dict) -> bool:
    """Returns True if the record has any silver-labeled entities."""
    return record["entity_count"] > 0


def is_high_confidence(record: dict) -> bool:
    """Returns True if there are no conflicts and at least on silver label is being agreed upon by both BERT and dict."""
    return (record["number_of_conflicts"] == 0) and ("both" in record["silver_source"])


def distinct_entity_types(record: dict) -> set[str]:
    """Returns the set of distinct entity types present in silver labels."""
    return set(
        [
            tag.split("-", 1)[1]
            for tag in record["silver_labels"]
            if tag.startswith("B-")
        ]
    )


def filter_unlabeled(records: list[dict]) -> list[dict]:
    """Drop records with no silver labels (no value as training data)."""
    kept = [r for r in records if has_any_label(r)]
    logger.info(
        "filter_unlabeled: %d/%d records kept (dropped %d with no labels)",
        len(kept),
        len(records),
        len(records) - len(kept),
    )
    return kept


def cap_per_source(
    records: list[dict],
    *,
    source_cap: int = SOURCE_CAP,
    seed: int | None = None,
) -> list[dict]:
    """Cap the number of sentences per source page (``record['title']``).

    Ensures the final sample isn't dominated by a handful of long wiki pages.
    """
    rng = random.Random(seed) if seed is not None else random
    grouped: dict[str, list[dict]] = defaultdict(list)
    for r in records:
        grouped[r["title"]].append(r)
    capped: list[dict] = []
    for group in grouped.values():
        rng.shuffle(group)
        capped.extend(group[: min(source_cap, len(group))])
    logger.info(
        "cap_per_source: %d/%d records kept (cap=%d per source, dropped %d)",
        len(capped),
        len(records),
        source_cap,
        len(records) - len(capped),
    )
    return capped


def stratified_sample(
    records: list[dict],
    *,
    targets: dict[str, int] = TARGETS,
    seed: int = 42,
) -> list[dict]:
    """Stratified sample by ``dominant_label``, falling back to CHAR for shortfalls."""
    rng = random.Random(seed)

    grouped: dict[str, list[dict]] = defaultdict(list)
    unclassified = 0
    for r in records:
        dom = dominant_label(r)
        if dom:
            grouped[dom].append(r)
        else:
            unclassified += 1
    if unclassified:
        logger.warning(
            "stratified_sample: %d records had no dominant label", unclassified
        )

    selected: list[dict] = []
    shortfall = 0
    for label, target in targets.items():
        bucket = grouped[label]
        take = min(len(bucket), target)
        selected.extend(bucket[:take])
        missing = target - take
        if missing > 0:
            shortfall += missing
            logger.warning(
                "stratified_sample: %s shortfall %d (target %d, available %d)",
                label,
                missing,
                target,
                len(bucket),
            )
        else:
            logger.info(
                "stratified_sample: %s target %d, available %d, taking %d",
                label,
                target,
                len(bucket),
                take,
            )

    # Fill the shortfall with CHARacters since they tend to be the largest pool.
    if shortfall:
        already = {r["id"] for r in selected}
        spare = [r for r in grouped["CHAR"] if r["id"] not in already]
        rng.shuffle(spare)
        selected.extend(spare[: min(shortfall, len(spare))])

    rng.shuffle(selected)
    logger.info("stratified_sample: final count %d", len(selected))
    if len(selected) < sum(targets.values()):
        logger.warning(
            "stratified_sample: total %d below targets sum %d",
            len(selected),
            sum(targets.values()),
        )
    return selected


def split_unique_per_annotator(
    all_unique: list[dict],
    annotators: list[str],
    rng: random.Random,
) -> dict[str, list[dict]]:
    """
    Splits unique (non-overlap) sentences evenly across annotators.
    Any remainder goes to the first annotator.
    """
    rng.shuffle(all_unique)
    n = len(all_unique)
    k = len(annotators)
    base = n // k
    remainder = n % k

    splits = {}
    start = 0
    for i, name in enumerate(annotators):
        extra = 1 if i < remainder else 0
        end = start + base + extra
        splits[name] = all_unique[start:end]
        start = end
    return splits
