"""Public annotation package API."""

from src.annotation.doccano_client import DoccanoClient
from src.annotation.merge import majority_vote, merge_records
from src.annotation.records import (
	iter_jsonl,
	normalize_record,
	read_normalized_jsonl,
	write_normalized_jsonl,
)
from src.annotation.types import AnnotationRecord, LabelSpan, RawRecord

__all__ = [
	"AnnotationRecord",
	"DoccanoClient",
	"LabelSpan",
	"RawRecord",
	"iter_jsonl",
	"majority_vote",
	"merge_records",
	"normalize_record",
	"read_normalized_jsonl",
	"write_normalized_jsonl",
]
