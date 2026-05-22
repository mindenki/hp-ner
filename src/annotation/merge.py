"""Merge annotation records via overlap-set majority voting."""

from collections import defaultdict

from src.annotation.types import AnnotationRecord


def resolve_overlap(
    records: list[AnnotationRecord],
    *,
    threshold: int = 3,
    overrides: dict[str, list[dict]] | None = None,
) -> tuple[AnnotationRecord, list[dict]]:
    """Majority-vote spans; emit unresolved conflicts as separate output.

    Args:
        records:   all annotator records for one sentence (same text).
        threshold: number of agreeing annotators needed to accept a span.
        overrides: optional ``{text: [span_dicts]}`` to skip prompting.

    Returns ``(merged_record, conflicts)``:
        - ``merged_record`` is ``{text, labels}`` with accepted spans.
        - ``conflicts`` is a list of ``{text, candidates}`` for the caller to
          resolve interactively (empty when nothing unresolved).
    """
    text = records[0]["text"]

    if overrides and text in overrides:
        return {"text": text, "labels": list(overrides[text])}, []

    vote_counts: dict[tuple[int, int, str], int] = defaultdict(int)
    for r in records:
        for span in r["labels"]:
            if isinstance(span, dict):
                key = (int(span["start"]), int(span["end"]), str(span["label"]))
            else:
                key = (int(span[0]), int(span[1]), str(span[2]))
            vote_counts[key] += 1

    accepted = [
        {"start": s, "end": e, "label": l}
        for (s, e, l), c in vote_counts.items()
        if c >= threshold
    ]
    accepted.sort(key=lambda d: (d["start"], d["end"], d["label"]))

    near_miss = [
        {"span": k, "count": c}
        for k, c in vote_counts.items()
        if 0 < c < threshold
    ]

    conflicts: list[dict] = []
    if not accepted and near_miss:
        conflicts.append({"text": text, "candidates": near_miss})

    return {"text": text, "labels": accepted}, conflicts
