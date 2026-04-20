"""Convert merged gold JSONL to IOB2 and produce a stratified 80/10/10 split.

Reads data/annotated/gold_merged.jsonl, converts Doccano char-offset annotations
back to IOB2 token labels, and produces a stratified train/dev/test split that
preserves entity-type distribution across splits.

Outputs (written to data/merged/ by default):
    train.iob2   ~80% of sentences
    dev.iob2     ~10% of sentences
    test.iob2    ~10% of sentences

Per-class entity counts are printed for each split so you can verify balance.

Usage:
    uv run python scripts/prepare_bert_split.py
    uv run python scripts/prepare_bert_split.py --input data/annotated/gold_merged.jsonl
"""

import argparse
import json
import sys
from pathlib import Path

from src.annotation.split import entity_count_stats, stratified_split
from src.preprocessing.iob2 import IOB2Writer, Sentence

# Reverse of the IOB2_TO_DOCCANO mapping in distribute.py
DOCCANO_TO_IOB2: dict[str, str] = {
    "Character":    "CHAR",
    "Location":     "LOC",
    "Organization": "ORG",
    "Creature":     "CREA",
    "Spell":        "SPELL",
    "Artifact":     "ARTI",
}


def doccano_to_sentence(record: dict) -> Sentence:
    """Convert a Doccano JSONL record to an IOB2 Sentence (whitespace tokenisation)."""
    text: str = record["text"]
    words = text.split()
    labels = ["O"] * len(words)

    # char position → token index
    char_to_token: dict[int, int] = {}
    pos = 0
    for i, word in enumerate(words):
        for j in range(len(word)):
            char_to_token[pos + j] = i
        pos += len(word) + 1

    for span in record.get("label", []):
        start, end, doccano_type = int(span[0]), int(span[1]), str(span[2])
        iob2_type = DOCCANO_TO_IOB2.get(doccano_type, doccano_type)

        token_indices: list[int] = []
        for char_pos in range(start, end):
            tok_idx = char_to_token.get(char_pos)
            if tok_idx is not None and (not token_indices or token_indices[-1] != tok_idx):
                token_indices.append(tok_idx)

        for k, tok_idx in enumerate(token_indices):
            labels[tok_idx] = f"B-{iob2_type}" if k == 0 else f"I-{iob2_type}"

    return Sentence(words=words, labels=labels)


def _print_stats(split_name: str, sentences: list[Sentence]) -> None:
    counts = entity_count_stats(sentences)
    total = sum(counts.values())
    print(f"\n  {split_name}: {len(sentences)} sentences, {total} entity spans")
    for etype, count in sorted(counts.items()):
        pct = count / total * 100 if total else 0
        print(f"    {etype:<10} {count:>5}  ({pct:5.1f}%)")


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("data/annotated/gold_merged.jsonl"),
        help="Merged gold JSONL file (default: data/annotated/gold_merged.jsonl)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/merged"),
        help="Output directory for IOB2 split files (default: data/merged)",
    )
    parser.add_argument("--train-ratio", type=float, default=0.8)
    parser.add_argument("--dev-ratio",   type=float, default=0.1)
    parser.add_argument("--seed",        type=int,   default=42)
    args = parser.parse_args()

    test_ratio = round(1.0 - args.train_ratio - args.dev_ratio, 10)
    if test_ratio < 0:
        print("Error: train-ratio + dev-ratio must be ≤ 1.0", file=sys.stderr)
        sys.exit(1)
    ratios = (args.train_ratio, args.dev_ratio, test_ratio)

    if not args.input.exists():
        print(f"Input file not found: {args.input}", file=sys.stderr)
        print("Run merge_annotations.py first.", file=sys.stderr)
        sys.exit(1)

    with args.input.open(encoding="utf-8") as f:
        sentences = [
            doccano_to_sentence(json.loads(line))
            for line in f
            if line.strip()
        ]

    print(f"Loaded {len(sentences)} sentences from {args.input}")

    train, dev, test = stratified_split(sentences, ratios=ratios, seed=args.seed)

    print(
        f"\nSplit ({args.train_ratio:.0%} / {args.dev_ratio:.0%} / {test_ratio:.0%})"
        " — entity counts per split:"
    )
    _print_stats("train", train)
    _print_stats("dev  ", dev)
    _print_stats("test ", test)

    writer = IOB2Writer(mode="generic", fix_transitions=True)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    writer.write(train, args.output_dir / "train.iob2")
    writer.write(dev,   args.output_dir / "dev.iob2")
    writer.write(test,  args.output_dir / "test.iob2")

    print(f"\nWritten to {args.output_dir}/")
    print("  train.iob2  dev.iob2  test.iob2")


if __name__ == "__main__":
    main()
