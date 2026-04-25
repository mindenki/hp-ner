"""Create annotator accounts and per-annotator Doccano projects on a shared server.

Run this ONCE after deploying Doccano to Azure (or any shared host).
It will:
  1. Create one Doccano user account per annotator (via docker exec on the server)
  2. Create one Doccano project per annotator
  3. Add the annotator as a member of their project
  4. Import overlap + personal JSONL batches into each project
  5. Assign examples to each annotator (after all imports are queued)

Prerequisites:
  - Doccano is running on the target machine (docker compose up -d)
  - SSH access to the machine where Doccano is running (for user creation)
  - JSONL batch files exist in --data-dir

Usage (against Azure VM):
    uv run python scripts/annotation/setup_team.py \\
        --base-url http://<azure-ip>:8000 \\
        --ssh-host <azure-ip> \\
        --ssh-user azureuser

Usage (local testing):
    uv run python scripts/annotation/setup_team.py --local
"""

import argparse
import logging
import subprocess
import sys
import time
from pathlib import Path

from src.annotation.doccano_client import DoccanoClient

logger = logging.getLogger(__name__)

ANNOTATORS = [
    {"username": "peter", "email": "peter@itu.dk", "password": "annotate2024"},
    {"username": "hanna", "email": "hanna@itu.dk", "password": "annotate2024"},
    {"username": "zita", "email": "zita@itu.dk", "password": "annotate2024"},
    {"username": "anis", "email": "anis@itu.dk", "password": "annotate2024"},
]

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


def create_django_user(
    username: str,
    email: str,
    password: str,
    ssh_host: str | None,
    ssh_user: str,
    container_name: str,
    local: bool,
) -> bool:
    """Create a Django user inside the Doccano container via docker exec."""
    python_snippet = (
        "from django.contrib.auth.models import User; "
        f"User.objects.filter(username='{username}').exists() or "
        f"User.objects.create_user('{username}', '{email}', '{password}')"
    )
    docker_cmd = [
        "docker",
        "exec",
        container_name,
        "python",
        "manage.py",
        "shell",
        "-c",
        python_snippet,
    ]

    if local or ssh_host is None:
        cmd = docker_cmd
    else:
        cmd = ["ssh", f"{ssh_user}@{ssh_host}", " ".join(docker_cmd)]

    logger.debug("Running: %s", " ".join(cmd))
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        logger.error(
            "Failed to create user '%s':\n  stdout: %s\n  stderr: %s",
            username,
            result.stdout.strip(),
            result.stderr.strip(),
        )
        return False

    logger.info("  User '%s' ready.", username)
    return True


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
    parser.add_argument("--admin-username", default="admin")
    parser.add_argument("--admin-password", default="hpner2024")
    parser.add_argument("--ssh-host", default=None)
    parser.add_argument("--ssh-user", default="azureuser")
    parser.add_argument("--container-name", default="doccano")
    parser.add_argument("--local", action="store_true")
    parser.add_argument("--data-dir", type=Path, default=Path("data/selected/gold"))
    parser.add_argument("--overlap-file", default="overlap.jsonl")
    parser.add_argument(
        "--import-scope",
        choices=("both", "overlap", "personal"),
        default="both",
    )
    parser.add_argument("--skip-users", action="store_true")
    parser.add_argument("--skip-import", action="store_true")
    parser.add_argument("--run-id", default=None)
    args = parser.parse_args()

    run_id = args.run_id or time.strftime("%Y%m%d_%H%M%S")

    # ── Step 1: Create user accounts ──────────────────────────────────────────
    if not args.skip_users:
        logger.info("=== Step 1: Creating annotator user accounts ===")
        for ann in ANNOTATORS:
            create_django_user(
                username=ann["username"],
                email=ann["email"],
                password=ann["password"],
                ssh_host=args.ssh_host,
                ssh_user=args.ssh_user,
                container_name=args.container_name,
                local=args.local,
            )
    else:
        logger.info("=== Step 1: Skipping user creation (--skip-users) ===")

    # ── Step 2: Connect to Doccano API ─────────────────────────────────────────
    logger.info("=== Step 2: Connecting to Doccano at %s ===", args.base_url)
    client = DoccanoClient(args.base_url, args.admin_username, args.admin_password)

    users = client.list_users()
    user_id_map = {u["username"]: u["id"] for u in users}
    logger.info("Found %d users: %s", len(users), list(user_id_map.keys()))

    # ── Step 3: Create projects, labels, members, queue imports ───────────────
    # Keep track of (project_id, user_id) for the assignment pass below.
    logger.info("=== Step 3: Creating projects and queueing imports ===")
    project_assignments: list[tuple[int, int]] = []  # (project_id, user_id)

    for ann in ANNOTATORS:
        username = ann["username"]
        project_name = f"HP-NER Gold - {username} - {run_id}"

        logger.info("--- Annotator: %s ---", username)
        project_id = client.create_project(project_name)

        logger.info("  Adding labels ...")
        for label in LABELS:
            client.add_label(project_id, label)

        user_id = user_id_map.get(username)
        if user_id is None:
            logger.warning("  User '%s' not found — skipping membership.", username)
        else:
            client.add_project_member(project_id, user_id, role="annotator")

        if not args.skip_import:
            import_files = []
            if args.import_scope in ("both", "overlap"):
                import_files.append((args.overlap_file, "overlap"))
            if args.import_scope in ("both", "personal"):
                import_files.append((f"{username}_unique.jsonl", "personal"))

            for filename, batch in import_files:
                path = args.data_dir / filename
                if not path.exists():
                    logger.error("  Required file not found: %s", path)
                    sys.exit(1)
                client.import_jsonl(
                    project_id,
                    path,
                    import_meta={"batch": batch, "annotator": username},
                )
                time.sleep(0.5)

            if user_id is not None:
                project_assignments.append((project_id, user_id))

    # ── Step 4: Wait for Celery to finish, then assign examples ───────────────
    # All imports are now queued. Wait here so Celery has time to process
    # all of them before we start assigning — avoids the race condition where
    # assign_examples_to_user runs before the import task completes.
    if project_assignments:
        logger.info("=== Step 4: Waiting for imports to complete ===")
        logger.info("  Waiting 10s for Celery to process all import tasks ...")
        time.sleep(10)

        logger.info("=== Step 5: Assigning examples to annotators ===")
        for project_id, user_id in project_assignments:
            username = next(
                ann["username"]
                for ann in ANNOTATORS
                if user_id_map.get(ann["username"]) == user_id
            )
            logger.info(
                "  Assigning examples to %s (project %s) ...", username, project_id
            )
            assigned = client.assign_examples_to_user(project_id, user_id)
            if assigned == 0:
                logger.warning(
                    "  Still 0 examples for project %s — import may have failed. "
                    "Check: docker logs doccano --tail 20",
                    project_id,
                )

    logger.info("=== Done ===")
    logger.info("Share this URL with your team: %s", args.base_url)
    logger.info(
        "Each annotator logs in with username=<their name>, password=%s",
        ANNOTATORS[0]["password"],
    )


if __name__ == "__main__":
    main()
