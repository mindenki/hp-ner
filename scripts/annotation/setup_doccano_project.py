"""Create the HP-NER annotation project in a running Doccano instance via REST API.

Creates a Sequence Labeling project, adds the six entity labels with keyboard
shortcuts and colours, then imports overlap + per-annotator unique JSONL files.

Run this script on YOUR OWN machine after starting Doccano with:
  cd doccano && docker compose up -d

Usage:
    uv run python scripts/annotation/setup_doccano_project.py --annotator peter
    uv run python scripts/annotation/setup_doccano_project.py --annotator peter --password mypassword
"""

import argparse
import logging
import sys
import time
from pathlib import Path

from src.annotation.doccano_client import DoccanoClient

logger = logging.getLogger(__name__)

LABELS = [
    {
        "text": "Character",
        "suffix_key": "c",
        "background_color": "#4A90D9",
        "text_color": "#ffffff",
    },
    {
        "text": "Location",
        "suffix_key": "l",
        "background_color": "#7CB342",
        "text_color": "#ffffff",
    },
    {
        "text": "Organization",
        "suffix_key": "o",
        "background_color": "#F4A335",
        "text_color": "#ffffff",
    },
    {
        "text": "Creature",
        "suffix_key": "r",
        "background_color": "#9C27B0",
        "text_color": "#ffffff",
    },
    {
        "text": "Spell",
        "suffix_key": "s",
        "background_color": "#E53935",
        "text_color": "#ffffff",
    },
    {
        "text": "Artifact",
        "suffix_key": "a",
        "background_color": "#00897B",
        "text_color": "#ffffff",
    },
]

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
        "--base-url", default="http://localhost:8000", help="Doccano base URL"
    )
    parser.add_argument("--username", default="admin")
    parser.add_argument("--password", default="hpner2024")
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path("data/selected/gold"),
        help="Directory containing the JSONL batch files (default: data/selected/gold)",
    )
    parser.add_argument(
        "--project-name",
        default="HP-NER Gold - {annotator}",
        help=(
            "Name of the Doccano project to create "
            "(default: HP-NER Gold - {annotator})"
        ),
    )
    parser.add_argument(
        "--annotator",
        default="peter",
        help="Annotator name used for <annotator>_unique.jsonl (default: peter)",
    )
    parser.add_argument(
        "--overlap-file",
        default="overlap.jsonl",
        help="Overlap JSONL filename to import for all annotators (default: overlap.jsonl)",
    )
    parser.add_argument(
        "--skip-import",
        action="store_true",
        help="Create project and labels but skip importing JSONL files",
    )
    args = parser.parse_args()
    project_name = args.project_name.format(annotator=args.annotator)

    import_files = [
        (args.overlap_file, "overlap"),
        (f"{args.annotator}_unique.jsonl", "personal"),
    ]

    logger.info("Connecting to Doccano at %s ...", args.base_url)
    client = DoccanoClient(args.base_url, args.username, args.password)

    project_id = client.create_project(project_name)

    logger.info("Adding labels ...")
    for label in LABELS:
        client.add_label(project_id, label)

    if not args.skip_import:
        logger.info("Importing JSONL files ...")
        for filename, batch in import_files:
            path = args.data_dir / filename
            if not path.exists():
                logger.error("Required import file not found: %s", path)
                sys.exit(1)
            client.import_jsonl(
                project_id,
                path,
                import_meta={
                    "batch": batch,
                    "annotator": args.annotator,
                },
            )
            time.sleep(0.5)

    logger.info(
        "Done. Open %s and navigate to '%s' to start annotating.",
        args.base_url,
        project_name,
    )


if __name__ == "__main__":
    main()
