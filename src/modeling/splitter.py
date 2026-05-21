import logging
import random
from dataclasses import dataclass
from pathlib import Path

from src.common.iob2 import Sentence, read_iob2

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SplitRatios:
    train: float
    dev: float
    test: float

    def __post_init__(self) -> None:
        total = self.train + self.dev + self.test
        if abs(total - 1.0) > 1e-6:
            raise ValueError(f"Split ratios must sum to 1.0 (got {total:.6f})")


def _entity_types_in(sentence: Sentence) -> tuple[str, ...]:
    """Stratification key — the sorted tuple of entity types present in the sentence."""
    types = {
        label.split("-", 1)[1]
        for label in sentence.labels
        if label != "O" and "-" in label
    }
    return tuple(sorted(types)) if types else ("__NONE__",)


def _stratified_partition(
    sentences: list[Sentence],
    ratios: SplitRatios,
    seed: int,
    min_per_stratum: int = 3,
) -> tuple[list[Sentence], list[Sentence], list[Sentence]]:
    """Partition sentences into train/dev/test, stratified by entity-type set.

    Strata with fewer than ``min_per_stratum`` members are folded into a single
    ``__RARE__`` bucket. Inside each stratum, sentences are shuffled with the
    given seed and split by the requested ratios; any remainder lands in train.
    """
    rng = random.Random(seed)

    buckets: dict[tuple[str, ...], list[Sentence]] = {}
    for sentence in sentences:
        buckets.setdefault(_entity_types_in(sentence), []).append(sentence)

    rare: list[Sentence] = []
    regular: dict[tuple[str, ...], list[Sentence]] = {}
    for key, members in buckets.items():
        if len(members) < min_per_stratum:
            rare.extend(members)
        else:
            regular[key] = members
    if rare:
        regular[("__RARE__",)] = rare
        logger.info(f"Pooled {len(rare)} sentences from rare strata into __RARE__")

    train: list[Sentence] = []
    dev: list[Sentence] = []
    test: list[Sentence] = []

    for key, members in regular.items():
        shuffled = members[:]
        rng.shuffle(shuffled)
        n = len(shuffled)
        n_test = max(1, round(n * ratios.test)) if n >= 3 else 0
        n_dev = max(1, round(n * ratios.dev)) if n >= 3 else 0
        # Ensure train gets at least one sample.
        if n_test + n_dev >= n:
            n_test = max(0, n - 2)
            n_dev = 1 if n - n_test >= 2 else 0

        test.extend(shuffled[:n_test])
        dev.extend(shuffled[n_test : n_test + n_dev])
        train.extend(shuffled[n_test + n_dev :])
        logger.debug(
            f"Stratum {key} ({n} sentences) -> train={n - n_test - n_dev} dev={n_dev} test={n_test}",
        )

    rng.shuffle(train)
    rng.shuffle(dev)
    rng.shuffle(test)
    return train, dev, test


def _write_iob2(sentences: list[Sentence], path: Path) -> None:
    """Write sentences in EWT-compatible 5-column IOB2."""
    lines: list[str] = []
    for sentence in sentences:
        for idx, (word, label) in enumerate(
            zip(sentence.words, sentence.labels), start=1
        ):
            lines.append(f"{idx}\t{word}\t{label}\t-\t-")
        lines.append("")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")
    logger.info(f"Wrote {len(sentences)} sentences to {path}")


def _log_split_stats(name: str, sentences: list[Sentence]) -> None:
    """Log sentence/token counts and per-class entity counts for one split."""
    token_count = sum(len(s.words) for s in sentences)
    class_counts: dict[str, int] = {}
    for sentence in sentences:
        for label in sentence.labels:
            if label.startswith("B-"):
                cls = label.split("-", 1)[1]
                class_counts[cls] = class_counts.get(cls, 0) + 1
    classes_str = ", ".join(
        f"{cls}={count}" for cls, count in sorted(class_counts.items())
    )
    logger.info(
        f"Split '{name}' — sentences={len(sentences)}  tokens={token_count}  "
        f"entities=[{classes_str if classes_str else 'none'}]",
    )


def split_gold_entrypoint(
    gold_path: Path,
    output_dir: Path,
    ratios: SplitRatios,
    seed: int,
) -> tuple[Path, Path, Path]:
    """Read ``gold_path``, stratify-split it, and write train/dev/test IOB2 files.

    Returns the three written paths.
    """
    logger.info(f"Splitting gold corpus: {gold_path}")
    sentences = read_iob2(gold_path)
    logger.info(f"Loaded {len(sentences)} sentences  ratios={ratios}  seed={seed}")

    train, dev, test = _stratified_partition(sentences, ratios, seed)

    train_path = output_dir / "train.iob2"
    dev_path = output_dir / "dev.iob2"
    test_path = output_dir / "test.iob2"
    _write_iob2(train, train_path)
    _write_iob2(dev, dev_path)
    _write_iob2(test, test_path)

    _log_split_stats("train", train)
    _log_split_stats("dev", dev)
    _log_split_stats("test", test)

    return train_path, dev_path, test_path
