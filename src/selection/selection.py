"""
    Helper functions for corpus selection.
"""

from collections import Counter
import random





def dominant_label(record: dict) -> str | None:
    """ Return the most common label in the record's silver tags, in case of ties,
        it preferes rarer labels (ARTI > CREA > SPELL > ORG > LOC > CHAR)
    """
    
    priority = ["ARTI", "CREA", "SPELL", "ORG", "LOC", "CHAR"]
    
    counts = Counter()
    for tag in record["silver_labels"]:
        if tag != "O":
            if tag.split("-")[0] == "B":
                label = tag.split("-")[1]
                counts[label] += 1
    if not counts:
        return None
    max_count = max(counts.values())
    candidates = [label for label, count in counts.items() if count == max_count]
    candidates.sort(key=lambda l: priority.index(l))
    
    return candidates[0] or None

def has_conflict(record: dict) -> bool:
    """ Returns True if the record has any BERT/dict conflicts in its silver labels. """
    return record["number_of_conflicts"] > 0

def has_any_label(record: dict) -> bool:
    """ Returns True if the record has any silver-labeled entities. """
    return record["entity_count"] > 0

def is_high_confidence(record: dict) -> bool:
    """ Returns True if there are no conflicts and at least on silver label is being agreed upon by both BERT and dict. """
    return (record["number_of_conflicts"] == 0) and ("both" in record["silver_source"])

def distinct_entity_types(record: dict) -> set[str]:
    """Returns the set of distinct entity types present in silver labels."""
    return set([tag.split("-", 1)[1] for tag in record["silver_labels"] if tag.startswith("B-")])


def split_unique_per_annotator(all_unique: list[dict], annotators: list[str],rng: random.Random,) -> dict[str, list[dict]]:
    """
    Splits unique (non-overlap) sentences evenly across annotators.
    Any remainder goes to the first annotator.
    """
    rng.shuffle(all_unique)
    n = len(all_unique)
    k = len(annotators)
    base = n // k
    remainder = n % k

    splits = {}
    start = 0
    for i, name in enumerate(annotators):
        extra = 1 if i < remainder else 0
        end = start + base + extra
        splits[name] = all_unique[start:end]
        start = end
    return splits

