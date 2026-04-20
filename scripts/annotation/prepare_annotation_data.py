"""Convert silver-labeled IOB2 to per-annotator JSONL batches for Doccano import.

Reads the silver-labeled IOB2 file produced by the silver labeling pipeline,
samples sentences stratified by entity type, and writes:
  - data/to_annotate/overlap_set.jsonl    (100 sentences, given to all annotators)
  - data/to_annotate/peter_unique.jsonl   (350 unique sentences per annotator)
  - data/to_annotate/hanna_unique.jsonl
  - data/to_annotate/zita_unique.jsonl
  - data/to_annotate/anis_unique.jsonl

The JSONL format includes silver labels as pre-annotations so annotators can
correct rather than start from scratch, which speeds up the workflow significantly.

Usage:
    uv run python scripts/prepare_annotation_data.py
    uv run python scripts/prepare_annotation_data.py --silver-iob2 data/silver/hp_silver.iob2
"""

import argparse
import sys
from pathlib import Path

from src.annotation.distribute import prepare_annotation_batches

ANNOTATORS = ["peter", "hanna", "zita", "anis"]


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--silver-iob2",
        type=Path,
        default=Path("data/silver/hp_silver.iob2"),
        help="Path to silver-labeled IOB2 file (default: data/silver/hp_silver.iob2)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/to_annotate"),
        help="Directory to write JSONL batches (default: data/to_annotate)",
    )
    parser.add_argument(
        "--overlap-n",
        type=int,
        default=100,
        help="Sentences shared by all annotators for IAA measurement (default: 100)",
    )
    parser.add_argument(
        "--unique-n",
        type=int,
        default=350,
        help="Unique sentences per annotator (default: 350)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for reproducibility (default: 42)",
    )
    args = parser.parse_args()

    if not args.silver_iob2.exists():
        print(f"Error: silver IOB2 file not found: {args.silver_iob2}", file=sys.stderr)
        print(
            "Run the silver labeling pipeline first:\n"
            "  uv run python scripts/run_silver_label.py",
            file=sys.stderr,
        )
        sys.exit(1)

    prepare_annotation_batches(
        silver_iob2_path=args.silver_iob2,
        output_dir=args.output_dir,
        annotators=ANNOTATORS,
        overlap_n=args.overlap_n,
        unique_n=args.unique_n,
        seed=args.seed,
    )

    print(
        f"\nNext step: distribute the files in {args.output_dir}/ to each annotator.\n"
        "Each person imports their file(s) into their local Doccano instance.\n"
        "See doccano/README.md for the full workflow."
    )


if __name__ == "__main__":
    main()
