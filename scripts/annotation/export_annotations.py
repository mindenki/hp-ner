"""Export per-annotator JSONL annotations from Doccano via REST API.

Lists all projects in the Doccano instance and exports each as a JSONL file to
data/annotated/. Handles both synchronous (older Doccano) and async (newer Doccano)
export APIs.

Usage:
    uv run python scripts/export_annotations.py
    uv run python scripts/export_annotations.py --project-ids 1 2
"""

import argparse
import sys
from pathlib import Path

from src.annotation.doccano_client import DoccanoClient


def main() -> None:
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
        print("No projects found. Have you set up Doccano yet?")
        sys.exit(1)

    for project in projects:
        pid = project["id"]
        safe_name = project["name"].lower().replace(" ", "_").replace("/", "-")
        output_path = args.output_dir / f"{safe_name}_export.jsonl"
        print(f"Exporting project '{project['name']}' (id={pid}) ...")
        client.export_project(pid, output_path)

    print(f"\nAll exports written to {args.output_dir}/")
    print("Next: run merge_annotations.py to combine into a gold corpus.")


if __name__ == "__main__":
    main()
