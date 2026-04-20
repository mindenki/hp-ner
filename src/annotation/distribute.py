"""Split silver-labeled sentences into per-annotator JSONL batches for Doccano.

Converts IOB2 token-level labels to Doccano character-offset format and stratifies
the sample by dominant entity type to preserve entity distribution across batches.
"""

from __future__ import annotations

import json
import random
from collections import defaultdict
from pathlib import Path

from src.preprocessing.iob2 import IOB2Reader, Sentence

# Maps IOB2 label suffixes used in silver labeling → Doccano display names
IOB2_TO_DOCCANO: dict[str, str] = {
    "CHAR": "Character",
    "LOC": "Location",
    "ORG": "Organization",
    "CREA": "Creature",
    "SPELL": "Spell",
    "ARTI": "Artifact",
}


def _char_offsets(words: list[str]) -> list[tuple[int, int]]:
    """Return (start, end) character offsets for each word when joined by spaces."""
    offsets: list[tuple[int, int]] = []
    pos = 0
    for word in words:
        offsets.append((pos, pos + len(word)))
        pos += len(word) + 1  # +1 for the space separator
    return offsets


def _extract_spans(words: list[str], labels: list[str]) -> list[list]:
    """Return [[char_start, char_end, entity_type], ...] for each IOB2 entity span."""
    offsets = _char_offsets(words)
    spans: list[list] = []
    i = 0
    while i < len(labels):
        if labels[i].startswith("B-"):
            etype = labels[i][2:]
            doccano_type = IOB2_TO_DOCCANO.get(etype, etype)
            start_char = offsets[i][0]
            j = i + 1
            while j < len(labels) and labels[j] == f"I-{etype}":
                j += 1
            end_char = offsets[j - 1][1]
            spans.append([start_char, end_char, doccano_type])
            i = j
        else:
            i += 1
    return spans


def sentence_to_doccano(sentence: Sentence) -> dict:
    """Convert an IOB2 Sentence to a Doccano JSONL record with char-offset labels."""
    text = " ".join(sentence.words)
    label = _extract_spans(sentence.words, sentence.labels)
    return {"text": text, "label": label}


def _dominant_type(sentence: Sentence) -> str:
    """Return the most frequent entity type in the sentence (used for stratification)."""
    counts: dict[str, int] = defaultdict(int)
    for label in sentence.labels:
        if label.startswith("B-"):
            counts[label[2:]] += 1
    if not counts:
        return "NONE"
    return max(counts, key=lambda k: counts[k])


def _stratified_sample(
    sentences: list[Sentence], n: int, rng: random.Random
) -> list[Sentence]:
    """Sample exactly n sentences preserving entity-type distribution."""
    bins: dict[str, list[Sentence]] = defaultdict(list)
    for s in sentences:
        bins[_dominant_type(s)].append(s)

    total = len(sentences)
    sampled: list[Sentence] = []
    remainder: list[Sentence] = []

    for bin_sentences in bins.values():
        k = max(1, round(len(bin_sentences) / total * n))
        shuffled = list(bin_sentences)
        rng.shuffle(shuffled)
        sampled.extend(shuffled[:k])
        remainder.extend(shuffled[k:])

    # Trim or top-up to exactly n
    rng.shuffle(remainder)
    if len(sampled) < n:
        sampled.extend(remainder[: n - len(sampled)])
    elif len(sampled) > n:
        rng.shuffle(sampled)
        sampled = sampled[:n]

    return sampled


def _write_jsonl(records: list[dict], path: Path) -> None:
    with path.open("w", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")


def prepare_annotation_batches(
    silver_iob2_path: Path,
    output_dir: Path,
    annotators: list[str],
    overlap_n: int = 100,
    unique_n: int = 350,
    seed: int = 42,
) -> None:
    """Split silver sentences into overlap + per-annotator JSONL batches.

    Args:
        silver_iob2_path: Path to the silver-labeled IOB2 file.
        output_dir:       Directory to write output JSONL files.
        annotators:       List of annotator names (determines number of unique batches).
        overlap_n:        Sentences shared by all annotators (for IAA measurement).
        unique_n:         Unique sentences per annotator.
        seed:             Random seed for reproducibility.
    """
    rng = random.Random(seed)
    reader = IOB2Reader(mode="generic", validate=False)
    sentences = reader.read(silver_iob2_path)

    entity_sentences = [
        s for s in sentences if any(label.startswith("B-") for label in s.labels)
    ]
    print(
        f"Loaded {len(sentences)} sentences; {len(entity_sentences)} have at least one entity."
    )

    total_needed = overlap_n + unique_n * len(annotators)
    if len(entity_sentences) < total_needed:
        raise ValueError(
            f"Not enough entity sentences: need {total_needed}, have {len(entity_sentences)}."
        )

    pool = _stratified_sample(entity_sentences, total_needed, rng)
    overlap = pool[:overlap_n]
    rest = pool[overlap_n:]

    output_dir.mkdir(parents=True, exist_ok=True)

    overlap_path = output_dir / "overlap_set.jsonl"
    _write_jsonl([sentence_to_doccano(s) for s in overlap], overlap_path)
    print(f"Wrote {len(overlap):>4} sentences (overlap)  → {overlap_path}")

    for i, name in enumerate(annotators):
        batch = rest[i * unique_n : (i + 1) * unique_n]
        out_path = output_dir / f"{name}_unique.jsonl"
        _write_jsonl([sentence_to_doccano(s) for s in batch], out_path)
        print(f"Wrote {len(batch):>4} sentences ({name:<8}) → {out_path}")
