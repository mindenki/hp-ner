"""Minimal Doccano REST API client shared by setup and export scripts.

Tested against the doccano/doccano Docker image (latest).
API notes for this version:
  - URLs have NO trailing slashes (v1/projects not v1/projects/)
  - NER labels are "span-types", not "labels"
  - CSRF requires both X-CSRFToken header AND Referer header on write requests
  - Import endpoint: v1/projects/{id}/upload
  - Export endpoint: v1/projects/{id}/download  (async task-based)
"""

from __future__ import annotations

import io
import time
import zipfile
from pathlib import Path

import requests


class DoccanoClient:
    def __init__(self, base_url: str, username: str, password: str) -> None:
        self.base = base_url.rstrip("/")
        self.session = requests.Session()
        self._login(username, password)

    def _login(self, username: str, password: str) -> None:
        resp = self.session.post(
            f"{self.base}/v1/auth/login/",
            json={"username": username, "password": password},
        )
        resp.raise_for_status()
        token = resp.json()["key"]
        # CSRF requires X-CSRFToken header + Referer on all write requests
        csrf = self.session.cookies.get("csrftoken", "")
        self.session.headers.update(
            {
                "Authorization": f"Token {token}",
                "X-CSRFToken": csrf,
                "Referer": f"{self.base}/",
            }
        )
        print("Authenticated.")

    # ── project management ──────────────────────────────────────────────────

    def create_project(self, name: str) -> int:
        resp = self.session.post(
            f"{self.base}/v1/projects",
            json={
                "name": name,
                "project_type": "SequenceLabeling",
                "resourcetype": "SequenceLabelingProject",
                "description": "HP-NER gold annotation — Harry Potter Named Entity Recognition",
                "guideline": "See doccano/README.md for annotation guidelines.",
                "allow_overlapping": False,
                "tags": [],
            },
        )
        resp.raise_for_status()
        project_id: int = resp.json()["id"]
        print(f"Created project '{name}' (id={project_id})")
        return project_id

    def list_projects(self) -> list[dict]:
        resp = self.session.get(
            f"{self.base}/v1/projects",
            headers={"Accept": "application/json"},
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("results", data) if isinstance(data, dict) else data

    # ── label management ────────────────────────────────────────────────────

    def add_label(self, project_id: int, label: dict) -> None:
        # In this Doccano version, NER labels are "span-types"
        resp = self.session.post(
            f"{self.base}/v1/projects/{project_id}/span-types",
            json=label,
        )
        resp.raise_for_status()
        print(f"  + label: {label['text']} (key: {label['suffix_key']})")

    # ── dataset import / export ─────────────────────────────────────────────

    def import_jsonl(self, project_id: int, filepath: Path) -> None:
        # Step 1: upload file via filepond to get a temporary upload ID
        with filepath.open("rb") as f:
            up = self.session.post(
                f"{self.base}/v1/fp/process/",
                files={"filepond": (filepath.name, f, "application/octet-stream")},
            )
        up.raise_for_status()
        upload_id = up.text.strip()  # filepond returns the ID as plain text

        # Step 2: trigger the async import task with the upload ID
        resp = self.session.post(
            f"{self.base}/v1/projects/{project_id}/upload",
            json={
                "uploadIds": [upload_id],
                "format": "JSONL",
                "task": "SequenceLabeling",
            },
        )
        resp.raise_for_status()
        task_id = resp.json().get("task_id")
        print(f"  Import queued: {filepath.name} (task={task_id})")

    def export_project(self, project_id: int, output_path: Path) -> None:
        """Export project annotations as JSONL (async task-based)."""
        resp = self.session.post(
            f"{self.base}/v1/projects/{project_id}/download",
            json={"format": "JSONL", "exportApproved": False},
        )
        resp.raise_for_status()
        payload = resp.json()
        task_id = payload.get("task_id") or payload.get("id")
        if not task_id:
            raise RuntimeError(f"No task id in download response: {payload}")
        self._poll_and_download(project_id, task_id, output_path)

    def _poll_and_download(
        self, project_id: int, task_id: str, output_path: Path
    ) -> None:
        for attempt in range(30):
            # Poll uses camelCase taskId param; returns file bytes when ready
            resp = self.session.get(
                f"{self.base}/v1/projects/{project_id}/download",
                params={"taskId": task_id},
            )
            resp.raise_for_status()

            content_type = resp.headers.get("Content-Type", "")
            if "application/json" in content_type:
                # Still processing — {"status": "Not ready"} or similar
                print(
                    f"  Export task {task_id}: not ready (attempt {attempt + 1}/30) ..."
                )
                time.sleep(3)
                continue

            # File returned directly once the Celery task completes.
            # Doccano wraps the JSONL in a zip archive.
            output_path.parent.mkdir(parents=True, exist_ok=True)
            if zipfile.is_zipfile(io.BytesIO(resp.content)):
                with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
                    jsonl_names = [n for n in zf.namelist() if n.endswith(".jsonl")]
                    if not jsonl_names:
                        raise RuntimeError(
                            f"No .jsonl file found in export zip: {zf.namelist()}"
                        )
                    output_path.write_bytes(zf.read(jsonl_names[0]))
            else:
                output_path.write_bytes(resp.content)
            print(f"  Downloaded -> {output_path}")
            return

        raise TimeoutError(f"Export task {task_id} did not finish within 90 seconds.")
