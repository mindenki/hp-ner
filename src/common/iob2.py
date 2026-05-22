"""Unified IOB2 reader/writer.

Replaces the two pre-existing implementations:
  - baseline/src/dataset.py::read_iob2 (5-column EWT)
  - src/preprocessing/iob2.py (generic two-column with validation)
"""
import logging
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class Sentence:
    words: list[str]
    labels: list[str]


def _entity_type(label: str) -> str | None:
    if label == "O":
        return None
    return label.split("-", 1)[1]


def _validate(sentence: Sentence) -> None:
    open_type: str | None = None
    for i, label in enumerate(sentence.labels):
        if label.startswith("B-"):
            open_type = _entity_type(label)
        elif label.startswith("I-"):
            etype = _entity_type(label)
            if open_type != etype:
                prev = sentence.labels[i - 1] if i > 0 else "START"
                raise ValueError(
                    f"Invalid IOB2 transition at token {i} "
                    f"({sentence.words[i]!r}): {prev!r} -> {label!r}"
                )
        else:
            open_type = None


def read_iob2(path: Path, *, validate: bool = True) -> list[Sentence]:
    """Read 2/3/5-column IOB2 (auto-detected per line)."""
    logger.info("Reading IOB2 from %s", path)
    sentences: list[Sentence] = []
    words: list[str] = []
    labels: list[str] = []

    with Path(path).open(encoding="utf-8") as fh:
        for raw in fh:
            line = raw.rstrip("\n")
            if line.lstrip().startswith("#"):
                continue
            if line.strip() == "":
                if words:
                    s = Sentence(words=words, labels=labels)
                    if validate:
                        _validate(s)
                    sentences.append(s)
                    words, labels = [], []
                continue
            parts = line.split()
            if len(parts) >= 5:
                word, label = parts[1], parts[2]
            elif len(parts) == 3:
                word, label = parts[1], parts[2]
            elif len(parts) == 2:
                word, label = parts[0], parts[1]
            else:
                logger.warning("Skipping malformed line in %s: %r", path, line)
                continue
            words.append(word)
            labels.append(label)

    if words:
        s = Sentence(words=words, labels=labels)
        if validate:
            _validate(s)
        sentences.append(s)

    logger.info("Loaded %d sentences from %s", len(sentences), path)
    return sentences


def write_iob2(
    sentences: list[Sentence], path: Path, *, ewt_columns: bool = True
) -> None:
    """Write sentences to IOB2. ewt_columns=True writes 5-column EWT format."""
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    for sentence in sentences:
        for idx, (word, label) in enumerate(
            zip(sentence.words, sentence.labels), start=1
        ):
            if ewt_columns:
                lines.append(f"{idx}\t{word}\t{label}\t-\t-")
            else:
                lines.append(f"{word}\t{label}")
        lines.append("")
    out.write_text("\n".join(lines), encoding="utf-8")
    logger.info("Wrote %d sentences to %s", len(sentences), out)
