"""Shared IOB2 reader and writer for both EWT and HP NER corpora.

Supports two file formats:
  generic — one token per line as "TOKEN\\tLABEL", blank-line sentence boundaries
  ewt     — 5-column CoNLL-U-style "ID TOKEN LABEL _ _", comment lines starting with #
"""

from dataclasses import dataclass
from pathlib import Path


@dataclass
class Sentence:
    words: list[str]
    labels: list[str]


def _entity_type(label: str) -> str | None:
    """Return the entity type from a B-/I- label, or None for O."""
    if label == "O":
        return None
    return label[2:]  # strips "B-" or "I-"


def _validate_transitions(sentence: Sentence) -> None:
    """Raise ValueError on illegal IOB2 transitions.

    Illegal transitions:
      O  -> I-X  (must open with B-)
      I-X -> I-Y (type mismatch; must open new entity with B-)
    """
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
                    f"('{sentence.words[i]}'): {prev!r} -> {label!r}"
                )
        else:  # O
            open_type = None


def _fix_transitions(labels: list[str]) -> list[str]:
    """Return a copy of labels with illegal I- transitions rewritten to B-."""
    fixed: list[str] = []
    open_type: str | None = None
    for label in labels:
        if label.startswith("B-"):
            open_type = _entity_type(label)
            fixed.append(label)
        elif label.startswith("I-"):
            etype = _entity_type(label)
            if open_type != etype:
                fixed.append(f"B-{etype}")
                open_type = etype
            else:
                fixed.append(label)
        else:
            open_type = None
            fixed.append(label)
    return fixed


class IOB2Reader:
    """Parse IOB2 files into Sentence objects.

    Args:
        mode:     "generic" for 2-column token\\tlabel files;
                  "ewt" for 5-column EWT files with # comment lines.
        validate: When True, raise ValueError on invalid B-/I- transitions.
    """

    def __init__(self, mode: str = "generic", validate: bool = True) -> None:
        if mode not in ("generic", "ewt"):
            raise ValueError(f"mode must be 'generic' or 'ewt', got {mode!r}")
        self.mode = mode
        self.validate = validate

    def read(self, path: Path) -> list[Sentence]:
        sentences: list[Sentence] = []
        words: list[str] = []
        labels: list[str] = []

        with path.open(encoding="utf-8") as fh:
            for line in fh:
                line = line.rstrip("\n")

                if self.mode == "ewt" and line.startswith("#"):
                    continue

                if line == "":
                    if words:
                        s = Sentence(words=words, labels=labels)
                        if self.validate:
                            _validate_transitions(s)
                        sentences.append(s)
                        words, labels = [], []
                else:
                    parts = line.split("\t")
                    if self.mode == "ewt":
                        words.append(parts[1])
                        labels.append(parts[2])
                    else:
                        words.append(parts[0])
                        labels.append(parts[1])

        if words:
            s = Sentence(words=words, labels=labels)
            if self.validate:
                _validate_transitions(s)
            sentences.append(s)

        return sentences


class IOB2Writer:
    """Serialize Sentence objects to IOB2 format.

    Args:
        mode:            "generic" (default) — 2-column "TOKEN\\tLABEL";
                         "ewt" — 3-column "IDX\\tTOKEN\\tLABEL" with 1-based per-sentence index,
                         compatible with span_f1.py.
        fix_transitions: When True, silently rewrite illegal I- labels to B- before writing.
                         When False (default), raise ValueError instead.
    """

    def __init__(self, mode: str = "generic", fix_transitions: bool = False) -> None:
        if mode not in ("generic", "ewt"):
            raise ValueError(f"mode must be 'generic' or 'ewt', got {mode!r}")
        self.mode = mode
        self.fix_transitions = fix_transitions

    def write(self, sentences: list[Sentence], path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as fh:
            for sentence in sentences:
                labels = sentence.labels
                if self.fix_transitions:
                    labels = _fix_transitions(labels)
                else:
                    _validate_transitions(Sentence(sentence.words, labels))
                for i, (word, label) in enumerate(zip(sentence.words, labels), start=1):
                    if self.mode == "ewt":
                        fh.write(f"{i}\t{word}\t{label}\n")
                    else:
                        fh.write(f"{word}\t{label}\n")
                fh.write("\n")
