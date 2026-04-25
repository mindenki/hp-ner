"""Minimal Doccano REST API client shared by setup and export scripts.

Tested against the doccano/doccano Docker image (latest).
API notes for this version:
  - URLs have NO trailing slashes (v1/projects not v1/projects/)
  - NER labels are "span-types", not "labels"
  - CSRF requires both X-CSRFToken header AND Referer header on write requests
  - Import endpoint: v1/projects/{id}/upload
  - Export source endpoint: v1/projects/{id}/examples (paginated)
  - Label map endpoint: v1/projects/{id}/span-types
"""

import io
import json
import logging
from pathlib import Path
from typing import Any, Iterator, TypedDict

import requests

from src.annotation.records import read_normalized_jsonl
from src.annotation.types import AnnotationRecord, LabelSpan


logger = logging.getLogger(__name__)


class ProjectInfo(TypedDict):
    id: int
    name: str


class ExportSplitStats(TypedDict):
    overlap: int
    personal: int
    unknown: int
    skipped: int


ROLE_IDS = {
    "project_admin": 1,
    "annotator": 2,
    "annotation_approver": 3,
}


class DoccanoClient:
    def __init__(self, base_url: str, username: str, password: str) -> None:
        """Initialize Doccano client, establish session and authenticate."""
        self.base = base_url.rstrip("/")
        self.session = requests.Session()
        self._login(username, password)

    def _login(self, username: str, password: str) -> None:
        """Authenticate and store token + CSRF for subsequent requests."""
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
        logger.info("Authenticated.")

    def create_project(self, name: str) -> int:
        """Create a new Doccano project with the given name and return its ID.

        It is used to upload annotation batches for each annotator.
        """
        resp = self.session.post(
            f"{self.base}/v1/projects",
            json={
                "name": name,
                "project_type": "SequenceLabeling",
                "resourcetype": "SequenceLabelingProject",
                "description": "HP-NER gold annotation — Harry Potter Named Entity Recognition",
                "guideline": "See doccano/README.md for annotation guidelines.",
                "collaborative_annotation": True,
                "allow_overlapping": False,
                "tags": [],
            },
        )
        resp.raise_for_status()
        project_id: int = resp.json()["id"]
        logger.info("Created project '%s' (id=%s)", name, project_id)
        return project_id

    def list_projects(self) -> list[ProjectInfo]:
        resp = self.session.get(
            f"{self.base}/v1/projects",
            headers={"Accept": "application/json"},
        )
        resp.raise_for_status()
        projects = resp.json()["results"]
        return [{"id": int(p["id"]), "name": str(p["name"])} for p in projects]

    def add_label(self, project_id: int, label: dict) -> None:
        """Add one NER label (span-type) to the project.

        Label dict example:
        {
            "text": "Spell",
            "suffix_key": "s",
            "background_color": "#E53935",
            "text_color": "#ffffff",
        }
        """
        # In this Doccano version, NER labels are "span-types"
        resp = self.session.post(
            f"{self.base}/v1/projects/{project_id}/span-types",
            json=label,
        )
        resp.raise_for_status()
        logger.info("  + label: %s (key: %s)", label["text"], label["suffix_key"])

    def import_jsonl(
        self,
        project_id: int,
        filepath: Path,
        import_meta: dict[str, Any],
    ) -> None:
        """Import a JSONL file and set required metadata for each record."""
        records = read_normalized_jsonl(filepath)

        payload_lines = []
        for record in records:
            payload = {
                "text": record["text"],
                "label": [
                    [span["start"], span["end"], span["label"]]
                    for span in record["labels"]
                ],
                "entity_types": record["entity_types"],
                "entity_count": record["entity_count"],
                "meta": dict(import_meta),
            }
            payload_lines.append(json.dumps(payload, ensure_ascii=False))

        payload_text = "\n".join(payload_lines) + "\n"
        if logger.isEnabledFor(logging.DEBUG):
            preview = payload_text
            if len(preview) > 4000:
                preview = preview[:4000] + "\n... [truncated]"
            logger.debug(
                "Import JSONL payload preview for %s:\n%s", filepath.name, preview
            )

        payload_bytes = payload_text.encode("utf-8")

        # Step 1: upload file via filepond to get a temporary upload ID
        up = self.session.post(
            f"{self.base}/v1/fp/process/",
            files={
                "filepond": (
                    filepath.name,
                    io.BytesIO(payload_bytes),
                    "application/jsonl",
                )
            },
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
        logger.info(
            "  Import queued: %s (%s records, task=%s)",
            filepath.name,
            len(records),
            task_id,
        )

    def export_project_split(
        self,
        project_id: int,
        overlap_output_path: Path | None,
        personal_output_path: Path | None,
        export_scope: str = "both",
    ) -> ExportSplitStats:
        """Export project entries and split them into overlap/personal JSONL files."""
        label_map = self._get_span_type_map(project_id)

        include_overlap = export_scope in {"both", "overlap"}
        include_personal = export_scope in {"both", "personal"}

        if include_overlap and overlap_output_path is None:
            raise ValueError(
                "overlap_output_path is required for export_scope='overlap'/'both'"
            )
        if include_personal and personal_output_path is None:
            raise ValueError(
                "personal_output_path is required for export_scope='personal'/'both'"
            )

        if overlap_output_path is not None:
            overlap_output_path.parent.mkdir(parents=True, exist_ok=True)
        if personal_output_path is not None:
            personal_output_path.parent.mkdir(parents=True, exist_ok=True)

        overlap = 0
        personal = 0
        unknown = 0
        skipped = 0

        overlap_file = (
            overlap_output_path.open("w", encoding="utf-8")
            if include_overlap and overlap_output_path is not None
            else None
        )
        personal_file = (
            personal_output_path.open("w", encoding="utf-8")
            if include_personal and personal_output_path is not None
            else None
        )
        try:
            for example in self._iter_project_examples(project_id):
                labels: list[LabelSpan] = []
                for ann in example["annotations"]:
                    start = int(ann["start_offset"])
                    end = int(ann["end_offset"])
                    label = label_map.get(int(ann["label"]), str(ann["label"]))
                    labels.append({"start": start, "end": end, "label": label})
                labels.sort(key=lambda x: (x["start"], x["end"], x["label"]))

                record: AnnotationRecord = {
                    "text": str(example["text"]),
                    "labels": labels,
                    "entity_types": sorted({span["label"] for span in labels}),
                    "entity_count": len(labels),
                    "meta": {**example.get("meta", {})},
                }

                batch = str(record["meta"].get("batch", "")).strip().lower()

                line_payload = {
                    "text": record["text"],
                    # Keep exported JSONL aligned with Doccano import schema.
                    "label": [
                        [span["start"], span["end"], span["label"]]
                        for span in record["labels"]
                    ],
                    "entity_types": record["entity_types"],
                    "entity_count": record["entity_count"],
                    "meta": record["meta"],
                }
                line = json.dumps(line_payload, ensure_ascii=False) + "\n"
                if batch == "overlap":
                    if overlap_file is not None:
                        overlap_file.write(line)
                        overlap += 1
                    else:
                        skipped += 1
                elif batch == "personal":
                    if personal_file is not None:
                        personal_file.write(line)
                        personal += 1
                    else:
                        skipped += 1
                else:
                    unknown += 1
        finally:
            if overlap_file is not None:
                overlap_file.close()
            if personal_file is not None:
                personal_file.close()

        return {
            "overlap": overlap,
            "personal": personal,
            "unknown": unknown,
            "skipped": skipped,
        }

    def _iter_project_examples(
        self,
        project_id: int,
        limit: int = 1000,
    ) -> Iterator[dict[str, Any]]:
        """Iterate over all examples (each dataset row) in the project, handling pagination."""
        offset = 0

        while True:
            resp = self.session.get(
                f"{self.base}/v1/projects/{project_id}/examples",
                params={"limit": limit, "offset": offset},
                headers={"Accept": "application/json"},
            )
            resp.raise_for_status()
            batch = resp.json()["results"]
            if not batch:
                break
            for item in batch:
                yield item
            offset += len(batch)
            if len(batch) < limit:
                break

    def _get_span_type_map(self, project_id: int) -> dict[int, str]:
        """Fetch the mapping of span-type IDs to their text labels for the given project."""
        resp = self.session.get(
            f"{self.base}/v1/projects/{project_id}/span-types",
            headers={"Accept": "application/json"},
        )
        resp.raise_for_status()
        data = resp.json()
        # Doccano can return either a paginated object ({"results": [...]})
        # or a plain list depending on version/configuration.
        items = data.get("results", []) if isinstance(data, dict) else data
        label_map: dict[int, str] = {}
        for item in items:
            label_map[int(item["id"])] = str(item["text"])
        return label_map

    def list_users(self) -> list[dict]:
        """Return all Doccano users visible to the admin account.

        Each entry has at least 'id' and 'username'.
        Requires admin privileges.
        """
        resp = self.session.get(
            f"{self.base}/v1/users",
            headers={"Accept": "application/json"},
        )
        resp.raise_for_status()
        data = resp.json()
        # Response may be paginated or a plain list depending on Doccano version
        if isinstance(data, list):
            return data
        return data.get("results", data)

    def add_project_member(
        self,
        project_id: int,
        user_id: int,
        role: str = "annotator",
    ) -> None:
        role_id = ROLE_IDS.get(role, 2)
        resp = self.session.post(
            f"{self.base}/v1/projects/{project_id}/members",
            json={"user": user_id, "role": role_id},
        )
        resp.raise_for_status()
        logger.info(
            "  Added user_id=%s to project %s as '%s'", user_id, project_id, role
        )

    def assign_examples_to_user(self, project_id: int, user_id: int) -> int:
        """Assign all examples in a project to a specific user, skipping existing assignments."""
        # Fetch already-assigned example IDs to avoid 400 on duplicates
        existing = set()
        r = self.session.get(
            f"{self.base}/v1/projects/{project_id}/assignments",
            params={"limit": 1000},
        )
        r.raise_for_status()
        for a in r.json()["results"]:
            existing.add(a["example"])

        offset = 0
        assigned = 0
        while True:
            r = self.session.get(
                f"{self.base}/v1/projects/{project_id}/examples",
                params={"limit": 100, "offset": offset},
            )
            r.raise_for_status()
            data = r.json()
            for example in data["results"]:
                if example["id"] not in existing:
                    self.session.post(
                        f"{self.base}/v1/projects/{project_id}/assignments",
                        json={"example": example["id"], "assignee": user_id},
                    ).raise_for_status()
                    assigned += 1
            if not data["next"]:
                break
            offset += 100

        logger.info("  Assigned %d examples to user_id=%s", assigned, user_id)
        return assigned

    def create_user(self, username: str, email: str, password: str) -> int:
        """Register a new Doccano user and return their user ID."""
        resp = self.session.post(
            f"{self.base}/v1/auth/registration/",
            json={
                "username": username,
                "email": email,
                "password1": password,
                "password2": password,
            },
        )
        resp.raise_for_status()
        logger.info("Created user '%s'", username)
        # Registration returns the token, not the user id — fetch it separately
        return self._get_user_id(username)

    def _get_user_id(self, username: str) -> int:
        """Return the Doccano user ID for the given username."""
        resp = self.session.get(
            f"{self.base}/v1/users",
            headers={"Accept": "application/json"},
        )
        resp.raise_for_status()
        for user in resp.json():
            if user["username"] == username:
                return int(user["id"])
        raise ValueError(f"User '{username}' not found after creation")
