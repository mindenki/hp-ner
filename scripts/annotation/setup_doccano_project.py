"""Create the HP-NER annotation project in a running Doccano instance via REST API.

Creates a Sequence Labeling project, adds the six entity labels with keyboard
shortcuts and colours, then imports the JSONL batch files from data/to_annotate/.

Run this script on YOUR OWN machine after starting Doccano with:
  cd doccano && docker compose up -d

Usage:
    uv run python scripts/setup_doccano_project.py
    uv run python scripts/setup_doccano_project.py --password mypassword
"""

import argparse
import sys
import time
from pathlib import Path

from src.annotation.doccano_client import DoccanoClient

LABELS = [
    {"text": "Character",    "suffix_key": "c", "background_color": "#4A90D9", "text_color": "#ffffff"},
    {"text": "Location",     "suffix_key": "l", "background_color": "#7CB342", "text_color": "#ffffff"},
    {"text": "Organization", "suffix_key": "o", "background_color": "#F4A335", "text_color": "#ffffff"},
    {"text": "Creature",     "suffix_key": "r", "background_color": "#9C27B0", "text_color": "#ffffff"},
    {"text": "Spell",        "suffix_key": "s", "background_color": "#E53935", "text_color": "#ffffff"},
    {"text": "Artifact",     "suffix_key": "a", "background_color": "#00897B", "text_color": "#ffffff"},
]

# Files to import, in order. Each annotator imports their own unique file.
IMPORT_FILES = [
    "overlap_set.jsonl",
    "peter_unique.jsonl",
    "hanna_unique.jsonl",
    "zita_unique.jsonl",
    "anis_unique.jsonl",
]


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--base-url", default="http://localhost:8000", help="Doccano base URL")
    parser.add_argument("--username", default="admin")
    parser.add_argument("--password", default="hpner2024")
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path("data/to_annotate"),
        help="Directory containing the JSONL batch files (default: data/to_annotate)",
    )
    parser.add_argument(
        "--project-name",
        default="HP-NER Gold Set",
        help="Name of the Doccano project to create (default: HP-NER Gold Set)",
    )
    parser.add_argument(
        "--skip-import",
        action="store_true",
        help="Create project and labels but skip importing JSONL files",
    )
    args = parser.parse_args()

    print(f"Connecting to Doccano at {args.base_url} ...")
    client = DoccanoClient(args.base_url, args.username, args.password)

    project_id = client.create_project(args.project_name)

    print("\nAdding labels ...")
    for label in LABELS:
        client.add_label(project_id, label)

    if not args.skip_import:
        print("\nImporting JSONL files ...")
        for filename in IMPORT_FILES:
            path = args.data_dir / filename
            if not path.exists():
                print(f"  WARNING: {path} not found, skipping")
                continue
            client.import_jsonl(project_id, path)
            time.sleep(0.5)

    print(
        f"\nDone. Open {args.base_url} and navigate to '{args.project_name}' to start annotating."
    )


if __name__ == "__main__":
    main()
