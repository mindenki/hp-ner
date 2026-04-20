"""Compute Cohen's κ inter-annotator agreement on the overlap sentence set.

Converts Doccano char-offset annotations to token-level IOB2 labels (whitespace
tokenisation), then computes Cohen's κ for every pair of annotators. Overlap
sentences are detected by matching the `text` field across export files.

Usage:
    uv run python scripts/compute_iaa.py data/annotated/*.jsonl
    uv run python scripts/compute_iaa.py \\
        data/annotated/zita_export.jsonl data/annotated/hanna_export.jsonl \\
        --names zita hanna
"""

import argparse
import json
import sys
from itertools import combinations
from pathlib import Path

from sklearn.metrics import cohen_kappa_score


def load_token_labels(jsonl_path: Path) -> dict[str, list[str]]:
    """Load a Doccano JSONL export and convert to token-level IOB2 labels.

    Sentences are keyed by their text string so they can be matched across
    annotator files without relying on Doccano-internal document IDs.
    """
    results: dict[str, list[str]] = {}

    with jsonl_path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            record = json.loads(line)
            text: str = record["text"]
            tokens = text.split()
            labels = ["O"] * len(tokens)

            # Build char-position → token-index map
            char_to_token: dict[int, int] = {}
            pos = 0
            for i, tok in enumerate(tokens):
                for j in range(len(tok)):
                    char_to_token[pos + j] = i
                pos += len(tok) + 1  # +1 for space

            for span in record.get("label", []):
                start, end, etype = int(span[0]), int(span[1]), str(span[2])
                seen_tokens: set[int] = set()
                first = True
                for char_pos in range(start, end):
                    tok_idx = char_to_token.get(char_pos)
                    if tok_idx is None or tok_idx in seen_tokens:
                        continue
                    seen_tokens.add(tok_idx)
                    if first:
                        labels[tok_idx] = f"B-{etype}"
                        first = False
                    else:
                        if labels[tok_idx] == "O":
                            labels[tok_idx] = f"I-{etype}"

            results[text] = labels

    return results


def compute_kappa(
    labels_a: dict[str, list[str]], labels_b: dict[str, list[str]]
) -> tuple[float, int]:
    """Compute Cohen's κ over sentences shared by both annotators.

    Returns (kappa, n_shared_sentences).
    """
    shared = sorted(set(labels_a) & set(labels_b))
    if not shared:
        raise ValueError("No shared sentences between the two files.")
    flat_a = [labels for text in shared for labels in labels_a[text]]
    flat_b = [labels for text in shared for labels in labels_b[text]]
    return cohen_kappa_score(flat_a, flat_b), len(shared)


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
        help="Per-annotator JSONL export files (2 or more)",
    )
    parser.add_argument(
        "--names",
        nargs="+",
        metavar="NAME",
        help="Annotator names corresponding to each file (default: use file stems)",
    )
    args = parser.parse_args()

    if len(args.files) < 2:
        print("Need at least 2 annotation files to compute IAA.", file=sys.stderr)
        sys.exit(1)

    names = args.names if args.names else [p.stem for p in args.files]
    if len(names) != len(args.files):
        print(
            "--names must have the same number of entries as the number of files.",
            file=sys.stderr,
        )
        sys.exit(1)

    print("Loading annotation files ...")
    all_labels: dict[str, dict[str, list[str]]] = {}
    for name, path in zip(names, args.files):
        all_labels[name] = load_token_labels(path)
        print(f"  {name}: {len(all_labels[name])} sentences")

    col_w = max(len(a) + len(b) + 4 for a, b in combinations(names, 2))
    header = f"  {'Pair':<{col_w}}  {'κ':>7}  {'#shared':>8}"
    print(
        f"\nCohen's κ (overlap sentences only):\n{header}\n  {'-' * (len(header) - 2)}"
    )

    for name_a, name_b in combinations(names, 2):
        try:
            kappa, n_shared = compute_kappa(all_labels[name_a], all_labels[name_b])
            pair = f"{name_a} vs {name_b}"
            print(f"  {pair:<{col_w}}  {kappa:7.4f}  {n_shared:>8}")
        except ValueError as e:
            print(f"  {name_a} vs {name_b}: {e}")

    print()
    print(
        "Interpretation: κ > 0.8 excellent | 0.6-0.8 substantial | < 0.6 moderate/fair"
    )


if __name__ == "__main__":
    main()
