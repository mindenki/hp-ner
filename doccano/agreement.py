import json
from itertools import combinations
from sklearn.metrics import cohen_kappa_score
import numpy as np


def get_token_offsets(text: str, tokens: list[str]) -> list[tuple[int, int]]:
    """Reconstruct character offsets for each token by scanning through the text."""
    offsets = []
    cursor = 0
    for token in tokens:
        start = text.index(token, cursor)
        end = start + len(token)
        offsets.append((start, end))
        cursor = end
    return offsets


def spans_to_iob2(tokens: list[str], text: str, spans: list) -> list[str]:
    """Map Doccano character-level spans to IOB2 using precomputed token offsets."""
    offsets = get_token_offsets(text, tokens)
    labels = ["O"] * len(tokens)

    for span_start, span_end, entity_type in spans:
        for i, (tok_start, tok_end) in enumerate(offsets):
            if tok_start == span_start:
                labels[i] = f"B-{entity_type}"
            elif tok_start > span_start and tok_end <= span_end:
                labels[i] = f"I-{entity_type}"

    return labels


def load_annotations(path: str) -> dict:
    """Load a Doccano export and return {sentence_id: iob2_label_list}."""
    annotations = {}
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            record = json.loads(line)
            annotations[record["id"]] = spans_to_iob2(record["text"], record["label"])
    return annotations


# Load each annotator's export file
annotators = {
    "Hanna": load_annotations("data/annotated/hanna.jsonl"),
    "Zita":  load_annotations("data/annotated/zita.jsonl"),
    "Anis":  load_annotations("data/annotated/anis.jsonl"),
    "Peter": load_annotations("data/annotated/peter.jsonl"),
}

# List of all id-s (only selects overlapping id-s, which should be all)
overlap_ids = set.intersection(*[set(a.keys()) for a in annotators.values()])

# Flatten all overlap sentences into one long label sequence per annotator
def get_flat_labels(annotations: dict, ids: set) -> list[str]:
    flat = []
    for sid in sorted(ids):   # sorted so order is identical for all annotators
        flat.extend(annotations[sid])
    return flat

flat = {name: get_flat_labels(ann, overlap_ids) for name, ann in annotators.items()}

# Compute pairwise kappa
kappas = {}
for (name_a, labels_a), (name_b, labels_b) in combinations(flat.items(), 2):
    pair = f"{name_a}–{name_b}"
    kappas[pair] = cohen_kappa_score(labels_a, labels_b)
    print(f"{pair}: κ = {kappas[pair]:.3f}")

mean_kappa = np.mean(list(kappas.values()))
print(f"\nMean pairwise K: {mean_kappa:.3f}")
print("Target K >= 0.7:", "True, annotation's good to go" if mean_kappa >= 0.7 else "False, re-annotation needed")