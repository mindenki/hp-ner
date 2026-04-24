"""Helpers for reading, normalizing, and writing annotation JSONL files."""

import json
from pathlib import Path
from typing import Iterable

from src.annotation.types import AnnotationRecord, LabelSpan, RawRecord


def _normalize_span(span: object) -> LabelSpan:
    """Normalize one raw span annotation to the required LabelSpan schema."""
    if isinstance(span, dict):
        if not {"start", "end", "label"}.issubset(span):
            raise ValueError(f"Invalid span dict format: {span!r}")
        start = int(span["start"])
        end = int(span["end"])
        label = str(span["label"])
        return LabelSpan(start=start, end=end, label=label)

    if not isinstance(span, (list, tuple)) or len(span) != 3:
        raise ValueError(f"Invalid span format: {span!r}")

    start = int(span[0])
    end = int(span[1])
    label = str(span[2])
    return LabelSpan(start=start, end=end, label=label)


def normalize_record(raw: RawRecord) -> AnnotationRecord:
    """Normalize one record to the project's required annotation schema."""
    required = ("text", "entity_types", "entity_count")
    missing = [key for key in required if key not in raw]
    if missing:
        raise ValueError(f"Record missing required keys {missing}: {raw}")

    if "labels" in raw:
        raw_spans = raw["labels"]
    elif "label" in raw:
        raw_spans = raw["label"]
    else:
        raise ValueError(f"Record missing required key 'label'/'labels': {raw}")

    text = str(raw["text"])

    labels = [_normalize_span(span) for span in raw_spans]
    labels.sort(key=lambda span: (span["start"], span["end"], span["label"]))

    entity_types = [str(value) for value in raw["entity_types"]]
    entity_count = int(raw["entity_count"])

    record = AnnotationRecord(
        text=text,
        labels=labels,
        entity_types=entity_types,
        entity_count=entity_count,
    )
    return record


def iter_jsonl(path: Path) -> Iterable[RawRecord]:
    """Yield raw JSON objects from a JSONL file, one per line."""
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError(f"Expected object JSON per line in {path}, got: {value!r}")
            yield value


def read_normalized_jsonl(path: Path) -> list[AnnotationRecord]:
    """Read a JSONL file and normalize each record to Doccano-compatible schema."""
    return [normalize_record(record) for record in iter_jsonl(path)]


def write_normalized_jsonl(records: Iterable[AnnotationRecord], path: Path) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            payload = {
                "text": record["text"],
                "label": [
                    [span["start"], span["end"], span["label"]]
                    for span in record["labels"]
                ],
                "entity_types": record["entity_types"],
                "entity_count": record["entity_count"],
                "meta": record["meta"]
            }
            handle.write(json.dumps(payload, ensure_ascii=False) + "\n")
            count += 1
    return count
