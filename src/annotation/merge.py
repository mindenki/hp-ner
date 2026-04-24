"""Merge annotation records, including overlap-set majority voting."""

from collections import defaultdict
from pathlib import Path

from src.annotation.records import read_normalized_jsonl, write_normalized_jsonl
from src.annotation.types import AnnotationRecord


def majority_vote(records: list[AnnotationRecord], threshold: int = 3) -> AnnotationRecord:
    """Merge multiple annotator records for one sentence via span-level voting."""
    text = records[0]["text"]

    vote_counts: dict[tuple[int, int, str], int] = defaultdict(int)
    for record in records:
        for span in record["labels"]:
            key = (span["start"], span["end"], span["label"])
            vote_counts[key] += 1

    labels = [
        {"start": start, "end": end, "label": etype}
        for (start, end, etype), count in vote_counts.items()
        if count >= threshold
    ]
    labels.sort(key=lambda span: (span["start"], span["end"], span["label"]))

    return {"text": text, "labels": labels}

def merge_records(
    personal_records: list[AnnotationRecord],
    overlap_records: list[AnnotationRecord],
    threshold: int = 3,
) -> list[AnnotationRecord]:
    """Merge personal records and overlap records into one gold dataset."""
    by_text: dict[str, list[AnnotationRecord]] = defaultdict(list)
    for record in personal_records:
        by_text[record["text"]].append(record)
    for record in overlap_records:
        by_text[record["text"]].append(record)

    merged: list[AnnotationRecord] = []
    for records in by_text.values():
        if len(records) > 1:
            merged.append(majority_vote(records, threshold=threshold))
        else:
            merged.append(records[0])

    merged.sort(key=lambda record: record["text"])
    return merged
