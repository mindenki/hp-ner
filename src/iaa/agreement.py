"""Inter-annotator agreement for the HP-NER overlap set."""
import json
import logging
from itertools import combinations
from pathlib import Path

import numpy as np
from sklearn.metrics import cohen_kappa_score

from src.common.spans import doccano_record_to_sentence

logger = logging.getLogger(__name__)


def _load_per_token_labels(path: Path) -> dict[int, list[str]]:
    """Load a Doccano overlap JSONL and return {sentence_id: per_token_iob2_labels}.

    Reuses src.common.spans.doccano_record_to_sentence — no local span/offset
    code; that lives in src/common/spans.py and is shared with
    scripts/finalize_gold.py.
    """
    out: dict[int, list[str]] = {}
    with Path(path).open(encoding="utf-8") as fh:
        for raw in fh:
            line = raw.strip()
            if not line:
                continue
            record = json.loads(line)
            sentence = doccano_record_to_sentence(record)  # no label_map: keep raw display labels
            out[int(record["id"])] = sentence.labels
    return out


def compute_iaa_entrypoint(
    overlap_paths: dict[str, Path],
    output_path: Path,
    *,
    threshold: float = 0.7,
) -> dict:
    """Compute mean pairwise Cohen's κ over annotators' overlap sets.

    Args:
        overlap_paths: ``{annotator_name: path_to_overlap_jsonl}``.
        output_path:   destination for the JSON report.
        threshold:    pass/fail cutoff for mean pairwise κ.

    Returns the same dict written to ``output_path``.
    """
    annotators = {name: _load_per_token_labels(p) for name, p in overlap_paths.items()}
    overlap_ids = set.intersection(*[set(a.keys()) for a in annotators.values()])
    if not overlap_ids:
        raise ValueError("No overlapping sentence IDs across annotators")

    flat = {
        name: [label for sid in sorted(overlap_ids) for label in ann[sid]]
        for name, ann in annotators.items()
    }

    pairwise: dict[str, float] = {}
    for (name_a, labels_a), (name_b, labels_b) in combinations(flat.items(), 2):
        pairwise[f"{name_a}-{name_b}"] = float(cohen_kappa_score(labels_a, labels_b))

    mean_kappa = float(np.mean(list(pairwise.values())))
    report = {
        "mean_pairwise_cohen_kappa": mean_kappa,
        "pairwise": pairwise,
        "threshold": threshold,
        "passes_threshold": mean_kappa >= threshold,
        "n_overlap_sentences": len(overlap_ids),
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    logger.info(
        "IAA: mean pairwise Cohen's kappa = %.3f (threshold %.2f, %s)",
        mean_kappa,
        threshold,
        "PASS" if report["passes_threshold"] else "FAIL",
    )
    return report
