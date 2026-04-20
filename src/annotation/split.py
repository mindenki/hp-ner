"""Stratified train/dev/test split for the HP-NER gold corpus.

Groups sentences by their entity-type signature (the set of entity types present)
and splits each group proportionally so that the distribution of entity types is
preserved across train, dev, and test sets.
"""

from __future__ import annotations

import random
from collections import defaultdict

from src.preprocessing.iob2 import Sentence


def _entity_signature(sentence: Sentence) -> frozenset[str]:
    """Return the set of entity types that appear in the sentence."""
    types: set[str] = set()
    for label in sentence.labels:
        if label.startswith("B-"):
            types.add(label[2:])
    return frozenset(types)


def stratified_split(
    sentences: list[Sentence],
    ratios: tuple[float, float, float] = (0.8, 0.1, 0.1),
    seed: int = 42,
) -> tuple[list[Sentence], list[Sentence], list[Sentence]]:
    """Split sentences into train/dev/test preserving entity-type distribution.

    Groups sentences by their entity-type signature and splits each group using
    the given ratios. Groups with fewer than 10 sentences are too small to split
    representatively and are assigned entirely to train.

    Args:
        sentences: All annotated sentences to split.
        ratios:    (train, dev, test) fractions summing to 1.0.
        seed:      Random seed for reproducibility.

    Returns:
        Three lists: (train_sentences, dev_sentences, test_sentences).
    """
    assert abs(sum(ratios) - 1.0) < 1e-6, "ratios must sum to 1.0"

    rng = random.Random(seed)

    bins: dict[frozenset[str], list[Sentence]] = defaultdict(list)
    for s in sentences:
        bins[_entity_signature(s)].append(s)

    train: list[Sentence] = []
    dev: list[Sentence] = []
    test: list[Sentence] = []

    train_r, dev_r, _ = ratios

    for group in bins.values():
        shuffled = list(group)
        rng.shuffle(shuffled)
        n = len(shuffled)

        if n < 10:
            # Too few to split representatively; put everything in train
            train.extend(shuffled)
            continue

        n_train = round(n * train_r)
        n_dev = round(n * dev_r)
        train.extend(shuffled[:n_train])
        dev.extend(shuffled[n_train : n_train + n_dev])
        test.extend(shuffled[n_train + n_dev :])

    return train, dev, test


def entity_count_stats(sentences: list[Sentence]) -> dict[str, int]:
    """Count entity span occurrences (B- labels) per entity type."""
    counts: dict[str, int] = defaultdict(int)
    for s in sentences:
        for label in s.labels:
            if label.startswith("B-"):
                counts[label[2:]] += 1
    return dict(counts)
