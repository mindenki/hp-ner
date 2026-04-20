"""Merge per-annotator Doccano JSONL exports into a single gold corpus.

Overlap sentences (same text in multiple files) are resolved via majority vote:
a span is kept only if at least --threshold annotators tagged the identical triple.
Unique sentences (appear in one file only) are passed through unchanged.

Output: data/annotated/gold_merged.jsonl

Usage:
    uv run python scripts/merge_annotations.py data/annotated/peter_export.jsonl \\
        data/annotated/hanna_export.jsonl data/annotated/zita_export.jsonl \\
        data/annotated/anis_export.jsonl
"""

import argparse
import sys
from pathlib import Path

from src.annotation.merge import merge_all


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "files",
        nargs="+",
        type=Path,
        metavar="JSONL",
        help="Per-annotator JSONL export files",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/annotated/gold_merged.jsonl"),
        help="Output path for merged gold corpus (default: data/annotated/gold_merged.jsonl)",
    )
    parser.add_argument(
        "--threshold",
        type=int,
        default=3,
        help="Min annotators who must agree on a span to keep it (default: 3 of 4)",
    )
    args = parser.parse_args()

    missing = [p for p in args.files if not p.exists()]
    if missing:
        for p in missing:
            print(f"File not found: {p}", file=sys.stderr)
        sys.exit(1)

    merge_all(args.files, args.output, threshold=args.threshold)
    print("\nNext: run prepare_bert_split.py to produce train/dev/test IOB2 splits.")


if __name__ == "__main__":
    main()
