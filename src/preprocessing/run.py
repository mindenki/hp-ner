"""Preprocessing orchestration: clean -> sentence-filter -> output JSONL.

One entry point called from ``scripts/prepare_annotation.py::_step_clean``.
"""
import logging
from pathlib import Path

from src.preprocessing.cleaner import clean_dataset
from src.preprocessing.sentence_filter import filter_dataset

logger = logging.getLogger(__name__)


def clean_entrypoint(raw_path: Path, cleaned_path: Path, filtered_path: Path) -> None:
    """Run cleaner then sentence-filter; write the filtered JSONL."""
    cleaned_path.parent.mkdir(parents=True, exist_ok=True)
    clean_dataset(raw_path, cleaned_path)
    filtered_path.parent.mkdir(parents=True, exist_ok=True)
    filter_dataset(cleaned_path, filtered_path)
    logger.info("clean_entrypoint: wrote %s", filtered_path)
