"""Annotation orchestration for scripts/prepare_annotation.py and finalize_gold.py.

Entry points:
  * setup_doccano_entrypoint(data_dir)   - create 4 Doccano projects + import JSONL
  * export_from_doccano_entrypoint(output_dir)    - pull per-annotator overlap/personal JSONL
  * merge_gold_entrypoint(...)        - majority-vote merge with conflict callback
  * write_iob2_entrypoint(...)         - convert merged records to silver/gold IOB2
"""
import json
import logging
import re
import time
import webbrowser
from collections.abc import Callable
from pathlib import Path

from src.annotation.doccano_client import DoccanoClient
from src.annotation.merge import resolve_overlap
from src.annotation.records import iter_jsonl
from src.common.iob2 import Sentence, write_iob2
from src.common.spans import DOCCANO_TO_IOB2, doccano_record_to_sentence

logger = logging.getLogger(__name__)

ANNOTATORS: list[str] = ["peter", "hanna", "zita", "anis"]

LABELS: list[dict] = [
    {"text": "Character",    "suffix_key": "c", "background_color": "#4A90D9", "text_color": "#ffffff"},
    {"text": "Location",     "suffix_key": "l", "background_color": "#7CB342", "text_color": "#ffffff"},
    {"text": "Organization", "suffix_key": "o", "background_color": "#F4A335", "text_color": "#ffffff"},
    {"text": "Creature",     "suffix_key": "r", "background_color": "#9C27B0", "text_color": "#ffffff"},
    {"text": "Spell",        "suffix_key": "s", "background_color": "#E53935", "text_color": "#ffffff"},
    {"text": "Artifact",     "suffix_key": "a", "background_color": "#00897B", "text_color": "#ffffff"},
]


def setup_doccano_entrypoint(
    data_dir: Path,
    *,
    base_url: str = "http://localhost:8000",
    username: str = "admin",
    password: str = "hpner2024",
    overlap_file: str = "overlap.jsonl",
    run_id: str | None = None,
    open_browser: bool = True,
) -> None:
    """Create one Doccano project per annotator with the 6 labels and import JSONL.

    ``data_dir`` must contain ``overlap.jsonl`` plus ``<annotator>_unique.jsonl``
    for each of the four annotators (the layout produced by
    ``select_gold_pool``).
    """
    run_id = run_id or time.strftime("%Y%m%d_%H%M%S")
    overlap_path = data_dir / overlap_file
    if not overlap_path.exists():
        raise FileNotFoundError(f"overlap file not found: {overlap_path}")

    logger.info("setup_doccano: connecting to %s as %s", base_url, username)
    client = DoccanoClient(base_url, username, password)

    for annotator in ANNOTATORS:
        unique_path = data_dir / f"{annotator}_unique.jsonl"
        if not unique_path.exists():
            raise FileNotFoundError(f"per-annotator file not found: {unique_path}")

        project_name = f"HP-NER Gold - {annotator} - {run_id}"
        logger.info("setup_doccano: creating project %r", project_name)
        project_id = client.create_project(project_name)

        for label in LABELS:
            client.add_label(project_id, label)

        for path, batch in [(overlap_path, "overlap"), (unique_path, "personal")]:
            client.import_jsonl(
                project_id,
                path,
                import_meta={"batch": batch, "annotator": annotator},
            )
            time.sleep(0.5)

        logger.info("setup_doccano: %s -> project %d", annotator, project_id)

    if open_browser:
        webbrowser.open(base_url)
    logger.info("setup_doccano: done — open %s to start annotating", base_url)


# ---------------------------------------------------------------------------
# export_from_doccano_entrypoint  (called by finalize_gold)
# ---------------------------------------------------------------------------

_PROJECT_NAME_RE = re.compile(r"HP-NER Gold - (?P<annotator>\w+) - .+")


def _annotator_from_project_name(name: str) -> str | None:
    """Extract the annotator slug from a setup_doccano_entrypoint-created project."""
    match = _PROJECT_NAME_RE.match(name)
    return match.group("annotator") if match else None


def export_from_doccano_entrypoint(
    output_dir: Path,
    *,
    base_url: str = "http://localhost:8000",
    username: str = "admin",
    password: str = "hpner2024",
) -> None:
    """Pull annotations from every HP-NER project, one pair per annotator.

    Output layout: ``<output_dir>/<annotator>_{overlap,personal}.jsonl``.
    Project names that don't match ``setup_doccano_entrypoint``'s naming
    convention are skipped (caller can pre-create such projects manually).
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    client = DoccanoClient(base_url, username, password)
    projects = client.list_projects()
    if not projects:
        raise RuntimeError(
            "No Doccano projects found. Run setup_doccano_entrypoint first."
        )

    for project in projects:
        annotator = _annotator_from_project_name(project["name"])
        if annotator is None:
            logger.info("export: skipping non-HP-NER project %r", project["name"])
            continue
        client.export_project_split(
            project["id"],
            overlap_output_path=output_dir / f"{annotator}_overlap.jsonl",
            personal_output_path=output_dir / f"{annotator}_personal.jsonl",
            export_scope="both",
        )
        logger.info("export: %s -> %s_{overlap,personal}.jsonl", project["name"], annotator)


# ---------------------------------------------------------------------------
# merge_gold_entrypoint  (called by finalize_gold)
# ---------------------------------------------------------------------------

def _load_overrides(path: Path) -> dict[str, list[dict]]:
    if not path.exists():
        return {}
    overrides: dict[str, list[dict]] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        overrides[row["text"]] = row["labels"]
    return overrides


def _write_overrides(overrides: dict[str, list[dict]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for text, labels in overrides.items():
            fh.write(json.dumps({"text": text, "labels": labels}) + "\n")


def merge_gold_entrypoint(
    annotated_dir: Path,
    overrides_path: Path,
    *,
    on_conflict: Callable[[str, list[dict]], list[dict]] | None = None,
    threshold: int = 3,
) -> list[dict]:
    """Group records by text across annotators, majority-vote spans, persist overrides.

    Reads ``<annotated_dir>/<annotator>_{personal,overlap}.jsonl`` files.
    ``on_conflict(text, candidates) -> resolved_spans`` is called for every
    text where the vote didn't reach ``threshold``. If ``on_conflict`` is None,
    conflicts are skipped with a warning (non-interactive mode).
    Returns the merged records (``{text, labels}``).
    """
    overrides = _load_overrides(overrides_path)

    per_text: dict[str, list[dict]] = {}
    for name in ANNOTATORS:
        for kind in ("personal", "overlap"):
            path = annotated_dir / f"{name}_{kind}.jsonl"
            if not path.exists():
                continue
            for record in iter_jsonl(path):
                if "label" in record and "labels" not in record:
                    record = dict(record, labels=record["label"])
                per_text.setdefault(record["text"], []).append(record)

    merged: list[dict] = []
    for text, recs in per_text.items():
        if len(recs) == 1:
            merged.append(recs[0])
            continue
        merged_rec, conflicts = resolve_overlap(recs, threshold=threshold, overrides=overrides)
        if conflicts:
            if on_conflict is None:
                logger.warning("merge: conflict skipped (non-interactive) on text %r", text)
            else:
                resolved = on_conflict(text, conflicts[0]["candidates"])
                merged_rec["labels"] = resolved
                overrides[text] = resolved
        merged.append(merged_rec)

    _write_overrides(overrides, overrides_path)
    return merged


# ---------------------------------------------------------------------------
# write_iob2_entrypoint  (called by finalize_gold)
# ---------------------------------------------------------------------------

def write_iob2_entrypoint(
    merged_gold: list[dict],
    *,
    silver_jsonl: Path,
    gold_iob2_out: Path,
    silver_iob2_out: Path,
) -> None:
    """Convert merged Doccano records into canonical gold + silver IOB2 files.

    Silver is the original silver JSONL with the gold-pool texts excluded.
    """
    gold_sentences = [
        doccano_record_to_sentence(r, label_map=DOCCANO_TO_IOB2) for r in merged_gold
    ]
    write_iob2(gold_sentences, gold_iob2_out, ewt_columns=True)

    gold_texts = {r["text"] for r in merged_gold}
    silver_sentences: list[Sentence] = []
    with silver_jsonl.open(encoding="utf-8") as fh:
        for line in fh:
            row = json.loads(line)
            text = row.get("text") or " ".join(row.get("tokens", []))
            if text in gold_texts:
                continue
            silver_sentences.append(Sentence(words=row["tokens"], labels=row["labels"]))
    write_iob2(silver_sentences, silver_iob2_out, ewt_columns=True)
