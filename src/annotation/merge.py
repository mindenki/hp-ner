"""Merge per-annotator Doccano JSONL exports into a single gold corpus.

Overlap sentences (same text in multiple files) are resolved via majority vote:
a span is retained only if at least `threshold` annotators agree on it.
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path


def majority_vote(records: list[dict], threshold: int = 3) -> dict:
    """Merge multiple annotator records for the same sentence.

    A span [start, end, type] is kept only if at least `threshold` annotators
    tagged an identical triple. Spans are sorted by start offset in the output.
    """
    text = records[0]["text"]

    vote_counts: dict[tuple[int, int, str], int] = defaultdict(int)
    for record in records:
        for span in record.get("label", []):
            key = (int(span[0]), int(span[1]), str(span[2]))
            vote_counts[key] += 1

    label = [
        [start, end, etype]
        for (start, end, etype), count in vote_counts.items()
        if count >= threshold
    ]
    label.sort(key=lambda x: x[0])

    return {"text": text, "label": label}


def merge_all(
    annotator_files: list[Path],
    output_path: Path,
    threshold: int = 3,
) -> None:
    """Merge per-annotator JSONL exports into a single gold corpus.

    Sentences that appear in multiple files (overlap set) are resolved via majority
    vote. Sentences that appear in only one file (unique sets) are passed through.

    Args:
        annotator_files: List of per-annotator JSONL export files.
        output_path:     Destination for the merged gold JSONL.
        threshold:       Minimum number of agreeing annotators to keep a span.
    """
    by_text: dict[str, list[dict]] = defaultdict(list)
    for path in annotator_files:
        with path.open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                record = json.loads(line)
                by_text[record["text"]].append(record)

    merged: list[dict] = []
    overlap_count = 0

    for text, records in by_text.items():
        if len(records) > 1:
            merged.append(majority_vote(records, threshold=threshold))
            overlap_count += 1
        else:
            merged.append(records[0])

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        for record in merged:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    total_in = sum(len(v) for v in by_text.values())
    print(f"Merged {total_in} records from {len(annotator_files)} files.")
    print(f"  Overlap sentences (majority vote, threshold={threshold}): {overlap_count}")
    print(f"  Total output sentences: {len(merged)}")
    print(f"  Written to: {output_path}")
