"""Typed structures for annotation records and spans."""

from typing import Any, NotRequired, TypedDict


class LabelSpan(TypedDict):
    """Character offset span for one entity annotation."""

    start: int
    end: int
    label: str


class AnnotationRecord(TypedDict):
    """Normalized Doccano-compatible sequence labeling record."""

    text: str
    labels: list[LabelSpan]
    entity_types: list[str]
    entity_count: int
    meta: NotRequired[dict[str, Any]]


RawRecord = dict[str, Any]
