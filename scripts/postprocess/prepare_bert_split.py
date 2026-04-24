"""Build train/dev/test IOB2 files for baseline training.

Pipeline:
1) Read silver-labeled records and split into train/dev
2) Read exported Doccano records (personal (4) + overlap)
3) Merge overlap records by majority vote across annotators
4) Build test set from merged gold records (personal + overlap)

Usage:
    uv run python scripts/postprocess/prepare_bert_split.py
"""

import argparse
from collections import defaultdict
import json
import random
import sys
from pathlib import Path
import logging

from src.annotation.merge import merge_records
from src.annotation.records import read_normalized_jsonl
from src.preprocessing.iob2 import IOB2Writer, Sentence

logger = logging.getLogger(__name__)

# Reverse of the IOB2_TO_DOCCANO mapping in distribute.py
DOCCANO_TO_IOB2: dict[str, str] = {
    "Character":    "CHAR",
    "Location":     "LOC",
    "Organization": "ORG",
    "Creature":     "CREA",
    "Spell":        "SPELL",
    "Artifact":     "ARTI",
}

def entity_count_stats(sentences: list[Sentence]) -> dict[str, int]:
    """Count entity span occurrences (B- labels) per entity type."""
    counts: dict[str, int] = defaultdict(int)
    for s in sentences:
        for label in s.labels:
            if label.startswith("B-"):
                counts[label[2:]] += 1
    return dict(counts)

def _labels_to_tuples(record: dict) -> list[tuple[int, int, str]]:
    labels = record.get("labels")
    spans: list[tuple[int, int, str]] = []
    for span in labels:
        if isinstance(span, dict):
            spans.append((int(span["start"]), int(span["end"]), str(span["label"])))
        else:
            spans.append((int(span[0]), int(span[1]), str(span[2])))
    return spans

def doccano_to_sentence(record: dict) -> Sentence:
    """Convert a Doccano JSONL record to an IOB2 sentence via whitespace tokens."""
    text: str = record["text"]
    words = text.split()
    labels = ["O"] * len(words)

    # char position -> token index
    char_to_token: dict[int, int] = {}
    pos = 0
    for i, word in enumerate(words):
        for j in range(len(word)):
            char_to_token[pos + j] = i
        pos += len(word) + 1

    for start, end, doccano_type in _labels_to_tuples(record):
        iob2_type = DOCCANO_TO_IOB2.get(doccano_type, doccano_type)

        token_indices: list[int] = []
        for char_pos in range(start, end):
            tok_idx = char_to_token.get(char_pos)
            # Only add token index if it's not None and not a duplicate of the last one (handles multi-char tokens)
            if tok_idx is not None and (not token_indices or token_indices[-1] != tok_idx):
                token_indices.append(tok_idx)

        for k, tok_idx in enumerate(token_indices):
            labels[tok_idx] = f"B-{iob2_type}" if k == 0 else f"I-{iob2_type}"

    return Sentence(words=words, labels=labels)

def silver_to_sentence(record: dict) -> Sentence:
    """Convert a silver JSONL record to an IOB2 sentence using tokens and silver_labels."""
    words = [str(token) for token in record.get("tokens", [])]
    labels = [str(label) for label in record.get("silver_labels", [])]
    if len(words) != len(labels):
        raise ValueError(
            f"Mismatched silver tokens/labels lengths: {len(words)} != {len(labels)}"
        )
    return Sentence(words=words, labels=labels)

def _dominant_type(sentence: Sentence) -> str:
    counts: dict[str, int] = {}
    for label in sentence.labels:
        if label.startswith("B-"):
            etype = label[2:]
            counts[etype] = counts.get(etype, 0) + 1
    if not counts:
        return "NONE"
    return max(counts, key=counts.get)

def _split_silver_guided_by_test(
    silver_sentences: list[Sentence],
    test_sentences: list[Sentence],
    train_ratio: float,
    seed: int,
) -> tuple[list[Sentence], list[Sentence]]:
    """Split silver into train/dev where dev follows gold-test entity distribution."""
    rng = random.Random(seed)
    dev_target_size = round(len(silver_sentences) * (1.0 - train_ratio))

    bins: dict[str, list[Sentence]] = {}
    for sentence in silver_sentences:
        dtype = _dominant_type(sentence)
        bins.setdefault(dtype, []).append(sentence)

    test_counts = entity_count_stats(test_sentences)
    total_test_spans = sum(test_counts.values())

    proportions = {
        label: count / total_test_spans
        for label, count in test_counts.items()
    }

    requested: dict[str, int] = {}
    for label, prop in proportions.items():
        requested[label] = round(dev_target_size * prop)

    # Ensure labels present in silver but absent in test are still allowed.
    for label in bins:
        requested.setdefault(label, 0)

    # Cap by available examples in each bin.
    for label, available in bins.items():
        requested[label] = min(requested.get(label, 0), len(available))

    current = sum(requested.values())
    labels = list(bins.keys())

    # Fill up to exact target size by adding from bins with remaining capacity.
    while current < dev_target_size:
        candidates = [
            label
            for label in labels if requested[label] < len(bins[label])
        ]
        if not candidates:
            break
        label = rng.choice(candidates)
        requested[label] += 1
        current += 1

    # Trim if rounding overshoots.
    while current > dev_target_size:
        candidates = [label for label in labels if requested[label] > 0]
        if not candidates:
            break
        label = rng.choice(candidates)
        requested[label] -= 1
        current -= 1

    dev: list[Sentence] = []
    train: list[Sentence] = []
    for label, sentences in bins.items():
        shuffled = list(sentences)
        rng.shuffle(shuffled)
        k = requested[label]
        dev.extend(shuffled[:k])
        train.extend(shuffled[k:])

    rng.shuffle(dev)
    rng.shuffle(train)
    return train, dev

def _print_stats(split_name: str, sentences: list[Sentence]) -> None:
    counts = entity_count_stats(sentences)
    total = sum(counts.values())
    logger.info(f"\n  {split_name}: {len(sentences)} sentences, {total} entity spans")
    for etype, count in sorted(counts.items()):
        pct = count / total * 100 if total else 0
        logger.info(f"    {etype:<10} {count:>5}  ({pct:5.1f}%)")


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
    )

    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--silver-input",
        type=Path,
        default=Path("data/silver/hp_silver.jsonl"),
        help="Silver JSONL file (default: data/silver/hp_silver.jsonl)",
    )
    parser.add_argument(
        "--personal-glob",
        default="data/annotated/*_personal.jsonl",
        help="Glob for personal exported gold files (default: data/annotated/*_personal.jsonl)",
    )
    parser.add_argument(
        "--overlap-glob",
        default="data/annotated/*_overlap.jsonl",
        help="Glob for overlap exported gold files (default: data/annotated/*_overlap.jsonl)",
    )
    parser.add_argument(
        "--overlap-threshold",
        type=int,
        default=3,
        help="Minimum annotators agreeing on overlap span (default: 3)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/merged"),
        help="Output directory for IOB2 split files (default: data/merged)",
    )
    parser.add_argument(
        "--silver-train-ratio",
        type=float,
        default=0.9,
        help="Train ratio for silver split; dev is 1-ratio (default: 0.9)",
    )
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    if not (0.0 < args.silver_train_ratio < 1.0):
        logger.error("Error: silver-train-ratio must be between 0 and 1.")
        sys.exit(1)

    if not args.silver_input.exists():
        logger.error(f"Silver input file not found: {args.silver_input}")
        sys.exit(1)

    personal_files = sorted(Path().glob(args.personal_glob))
    overlap_files = sorted(Path().glob(args.overlap_glob))
    if not personal_files:
        logger.error(f"No personal gold files found with glob: {args.personal_glob}")
        sys.exit(1)
    if not overlap_files:
        logger.error(f"No overlap gold files found with glob: {args.overlap_glob}")
        sys.exit(1)

    with args.silver_input.open(encoding="utf-8") as handle:
        silver_sentences = [
            silver_to_sentence(json.loads(line))
            for line in handle if line.strip()
        ]

    logger.info(f"Loaded {len(silver_sentences)} silver sentences from {args.silver_input}")

    personal_records = [
        record
        for path in personal_files
        for record in read_normalized_jsonl(path)
    ]
    overlap_records = [
        record
        for path in overlap_files
        for record in read_normalized_jsonl(path)
    ]

    merged_gold = merge_records(
        personal_records=personal_records,
        overlap_records=overlap_records,
        threshold=args.overlap_threshold,
    )

    gold_test_sentences = [doccano_to_sentence(record) for record in merged_gold]

    logger.info(
        f"\nGold test set - "
        f"personal files: {len(personal_files)}, overlap files: {len(overlap_files)}, "
        f"merged sentences: {len(gold_test_sentences)}"
    )

    silver_dev_ratio = round(1.0 - args.silver_train_ratio, 10)
    silver_train, silver_dev = _split_silver_guided_by_test(
        silver_sentences=silver_sentences,
        test_sentences=gold_test_sentences,
        train_ratio=args.silver_train_ratio,
        seed=args.seed,
    )

    logger.info(
        f"\nSilver split ({args.silver_train_ratio:.0%} / {silver_dev_ratio:.0%})"
        " guided by gold test distribution - entity counts per split:"
    )
    _print_stats("train", silver_train)
    _print_stats("dev  ", silver_dev)
    _print_stats("test ", gold_test_sentences)

    writer = IOB2Writer(mode="generic", fix_transitions=True)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    writer.write(silver_train, args.output_dir / "train.iob2")
    writer.write(silver_dev, args.output_dir / "dev.iob2")
    writer.write(gold_test_sentences, args.output_dir / "test.iob2")

    logger.info(f"\nWritten to {args.output_dir}/")
    logger.info("  train.iob2  dev.iob2  test.iob2")


if __name__ == "__main__":
    main()
