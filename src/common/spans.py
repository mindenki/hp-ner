"""Char-offset <-> IOB2 token-label conversions.

Used by:
  - src/iaa/agreement.py (per-token labels for kappa computation)
  - scripts/finalize_gold.py (Doccano records -> IOB2 Sentences)
  - scripts/prepare_annotation.py (IOB2 tags -> Doccano character spans)
"""
import logging
from collections.abc import Iterable

from src.common.iob2 import Sentence

logger = logging.getLogger(__name__)


# Mapping between Doccano display labels and the internal IOB2 entity types.
# One source of truth, consumed in both directions.
IOB2_TO_DOCCANO: dict[str, str] = {
    "CHAR": "Character",
    "LOC": "Location",
    "ORG": "Organization",
    "CREA": "Creature",
    "SPELL": "Spell",
    "ARTI": "Artifact",
}
DOCCANO_TO_IOB2: dict[str, str] = {v: k for k, v in IOB2_TO_DOCCANO.items()}


def token_offsets(text: str, tokens: list[str]) -> list[tuple[int, int]]:
    """Reconstruct character offsets for each whitespace-split token in text.

    Scans forward through text so repeated tokens map to their later occurrences.
    """
    offsets: list[tuple[int, int]] = []
    cursor = 0
    for token in tokens:
        start = text.index(token, cursor)
        end = start + len(token)
        offsets.append((start, end))
        cursor = end
    return offsets


def spans_to_iob2(
    tokens: list[str],
    text: str,
    spans: Iterable[tuple[int, int, str]],
) -> list[str]:
    """Convert Doccano-style (start_char, end_char, entity_type) spans into
    per-token IOB2 labels for ``tokens``.
    """
    offsets = token_offsets(text, tokens)
    labels = ["O"] * len(tokens)
    for span_start, span_end, entity_type in spans:
        for i, (tok_start, tok_end) in enumerate(offsets):
            if tok_start == span_start:
                labels[i] = f"B-{entity_type}"
            elif tok_start > span_start and tok_end <= span_end:
                labels[i] = f"I-{entity_type}"
    return labels


def _normalize_spans(raw_spans) -> list[tuple[int, int, str]]:
    """Doccano exports use either dict spans or [start, end, label] lists; normalize."""
    out: list[tuple[int, int, str]] = []
    for s in raw_spans:
        if isinstance(s, dict):
            out.append((int(s["start"]), int(s["end"]), str(s["label"])))
        else:
            out.append((int(s[0]), int(s[1]), str(s[2])))
    return out


def doccano_record_to_sentence(
    record: dict,
    *,
    label_map: dict[str, str] | None = None,
) -> Sentence:
    """Turn one Doccano JSONL record into a Sentence with IOB2 labels.

    Whitespace tokenisation matches what the annotators saw in Doccano. If
    ``label_map`` is given (e.g. {"Character": "CHAR"}), span labels are
    mapped before becoming IOB2 prefixes.
    """
    text: str = record["text"]
    tokens = text.split()
    raw_spans = record.get("labels", record.get("label", []))
    spans = _normalize_spans(raw_spans)
    if label_map:
        spans = [(s, e, label_map.get(lab, lab)) for s, e, lab in spans]
    return Sentence(words=tokens, labels=spans_to_iob2(tokens, text, spans))


def iob2_to_doccano_spans(
    tokens: list[str],
    text: str,
    tags: list[str],
    *,
    label_map: dict[str, str] | None = None,
) -> list[list]:
    """Convert per-token IOB2 ``tags`` to Doccano character-offset spans.

    Inverse of ``spans_to_iob2``. Returns ``[[start, end, label], ...]`` suitable
    for Doccano JSONL import. If ``label_map`` is given (e.g.
    ``IOB2_TO_DOCCANO``), entity types are translated to display labels.
    """
    offsets = token_offsets(text, tokens)
    out: list[list] = []
    i = 0
    while i < len(tokens):
        if not tags[i].startswith("B-"):
            i += 1
            continue
        entity_type = tags[i][2:]
        span_start = offsets[i][0]
        span_end = offsets[i][1]
        j = i + 1
        while j < len(tokens) and tags[j] == f"I-{entity_type}":
            span_end = offsets[j][1]
            j += 1
        display = label_map.get(entity_type, entity_type) if label_map else entity_type
        out.append([span_start, span_end, display])
        i = j
    return out
