"""Export per-annotator JSONL annotations from Doccano via REST API.

Lists projects in the Doccano instance and exports each as JSONL files split into:
    - <project>_overlap.jsonl  (for inter-annotator agreement)
    - <project>_personal.jsonl (annotator-unique sentences)

Separation is based on metadata added during import:
    meta.batch = "overlap" or "personal"

Usage:
    uv run python scripts/annotation/export_annotations.py
    uv run python scripts/annotation/export_annotations.py --project-ids 1 2
"""

import argparse
import logging
import sys
from pathlib import Path

from src.annotation.doccano_client import DoccanoClient


logger = logging.getLogger(__name__)


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
    )

    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--username", default="admin")
    parser.add_argument("--password", default="hpner2024")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/annotated"),
        help="Directory to write exported JSONL files (default: data/annotated)",
    )
    parser.add_argument(
        "--project-ids",
        nargs="+",
        type=int,
        metavar="ID",
        help="Specific project IDs to export (default: all projects)",
    )
    args = parser.parse_args()

    args.output_dir.mkdir(parents=True, exist_ok=True)
    client = DoccanoClient(args.base_url, args.username, args.password)

    projects = client.list_projects()
    if args.project_ids:
        projects = [p for p in projects if p["id"] in args.project_ids]

    if not projects:
        logger.error(
            "No projects found. Set up and import a project first, e.g.: "
            "uv run python scripts/annotation/setup_doccano_project.py --annotator peter"
        )
        sys.exit(1)

    for project in projects:
        pid = project["id"]
        safe_name = project["name"].lower().replace(" ", "_").replace("/", "-")
        
        overlap_path = args.output_dir / f"{safe_name}_overlap.jsonl"
        personal_path = args.output_dir / f"{safe_name}_personal.jsonl"
        
        logger.info("Exporting project '%s' (id=%s) ...", project["name"], pid)
        stats = client.export_project_split(pid, overlap_path, personal_path)

        logger.info(
            "  Split exported records -> overlap: %s, personal: %s",
            stats["overlap"],
            stats["personal"],
        )
        if stats["unknown"]:
            logger.warning(
                "  %s records missing meta.batch; re-run setup/import with updated script "
                "to preserve split metadata.",
                stats["unknown"],
            )

    logger.info("All exports written to %s/", args.output_dir)
    logger.info(
        "Next: run scripts/postprocess/prepare_bert_split.py to build train/dev/test IOB2 files."
    )


if __name__ == "__main__":
    main()
