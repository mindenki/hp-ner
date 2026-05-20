from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from baseline.src.splitter import SplitRatios, split_gold

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

logger = logging.getLogger(__name__)


def _setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[logging.StreamHandler(sys.stdout)],
    )


def main() -> None:
    _setup_logging()

    parser = argparse.ArgumentParser(
        description="Stratified 80/10/10 split of HP gold IOB2."
    )
    parser.add_argument(
        "--input",
        default=str(_PROJECT_ROOT / "data/selected/gold/gold.iob2"),
        help="Path to the gold IOB2 file (default: data/selected/gold/gold.iob2)",
    )
    parser.add_argument(
        "--output-dir",
        default=str(_PROJECT_ROOT / "data/selected/gold"),
        help="Directory to write train.iob2, dev.iob2, test.iob2 (default: data/selected/gold)",
    )
    parser.add_argument("--train", type=float, default=0.8)
    parser.add_argument("--dev", type=float, default=0.1)
    parser.add_argument("--test", type=float, default=0.1)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    ratios = SplitRatios(train=args.train, dev=args.dev, test=args.test)
    split_gold(
        gold_path=Path(args.input),
        output_dir=Path(args.output_dir),
        ratios=ratios,
        seed=args.seed,
    )


if __name__ == "__main__":
    main()
