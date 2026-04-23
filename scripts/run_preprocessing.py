"""
S4 - Preprocessing

Runs cleaner and sentence filtering in sequence.

Usage (from project root):
    uv run scripts/run_preprocessing.py
    uv run scripts/run_preprocessing.py --input data/raw/wiki_data_v02.jsonl
    uv run scripts/run_preprocessing.py --clean-output data/clean/wiki_data_clean.jsonl --filtered-output data/clean/wiki_data_filtered.jsonl
"""

import argparse
import sys
from pathlib import Path

import spacy

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.preprocessing.cleaner import clean_dataset
from src.preprocessing.sentence_filter import filter_dataset


def parse_args():
    parser = argparse.ArgumentParser(description="S4 Preprocessing")
    parser.add_argument(
        "--input",
        default="data/raw/wiki_data.jsonl",
        help="Path to raw jsonl input.",
    )
    parser.add_argument(
        "--clean-output",
        default="data/clean/wiki_data_clean.jsonl",
        help="Path where cleaned records are written.",
    )
    parser.add_argument(
        "--filtered-output",
        default="data/clean/wiki_data_filtered.jsonl",
        help="Path where sentence-filtered records are written.",
    )
    parser.add_argument(
        "--skip-clean",
        action="store_true",
        help="Skip cleaner step and only run sentence filtering.",
    )
    parser.add_argument(
        "--skip-filter",
        action="store_true",
        help="Skip sentence filtering step.",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    input_path = Path(args.input)
    clean_output = Path(args.clean_output)
    filtered_output = Path(args.filtered_output)

    if args.skip_clean and args.skip_filter:
        raise ValueError("Both --skip-clean and --skip-filter are set, nothing to run.")

    if not args.skip_clean:
        clean_output.parent.mkdir(parents=True, exist_ok=True)

        nlp_clean = spacy.blank("en")
        nlp_clean.add_pipe("sentencizer")

        cleaned, dropped_clean = clean_dataset(input_path, clean_output, nlp_clean)
        print(f"[cleaner] input={input_path}")
        print(f"[cleaner] output={clean_output}")
        print(f"[cleaner] kept={len(cleaned)} dropped={len(dropped_clean)}")

    if not args.skip_filter:
        filtered_output.parent.mkdir(parents=True, exist_ok=True)

        filter_input = clean_output if not args.skip_clean else input_path
        nlp_filter = spacy.blank("en")

        cleaned_sentences, dropped_sentences = filter_dataset(
            filter_input,
            filtered_output,
            nlp=nlp_filter,
        )
        print(f"[sentence_filter] input={filter_input}")
        print(f"[sentence_filter] output={filtered_output}")
        print(
            f"[sentence_filter] kept={len(cleaned_sentences)} dropped={len(dropped_sentences)}"
        )


if __name__ == "__main__":
    main()
