from src.annotation.merge import resolve_overlap


def test_unanimous_span_kept_without_prompting():
    records = [
        {"text": "Harry went to Hogwarts.", "labels": [[0, 5, "Character"]]},
        {"text": "Harry went to Hogwarts.", "labels": [[0, 5, "Character"]]},
        {"text": "Harry went to Hogwarts.", "labels": [[0, 5, "Character"]]},
        {"text": "Harry went to Hogwarts.", "labels": [[0, 5, "Character"]]},
    ]
    merged, conflicts = resolve_overlap(records, threshold=3)
    assert merged["labels"] == [{"start": 0, "end": 5, "label": "Character"}]
    assert conflicts == []


def test_2_2_tie_reported_as_conflict():
    records = [
        {"text": "Gryffindor team", "labels": [[0, 10, "Organization"]]},
        {"text": "Gryffindor team", "labels": [[0, 10, "Organization"]]},
        {"text": "Gryffindor team", "labels": [[0, 15, "Organization"]]},
        {"text": "Gryffindor team", "labels": [[0, 15, "Organization"]]},
    ]
    merged, conflicts = resolve_overlap(records, threshold=3)
    assert merged["labels"] == []
    assert len(conflicts) == 1
    assert {c["span"] for c in conflicts[0]["candidates"]} >= {
        (0, 10, "Organization"),
        (0, 15, "Organization"),
    }


def test_override_applied_skips_prompt():
    records = [
        {"text": "X Y Z", "labels": [[0, 1, "A"]]},
        {"text": "X Y Z", "labels": [[0, 3, "B"]]},
    ]
    overrides = {"X Y Z": [{"start": 0, "end": 1, "label": "A"}]}
    merged, conflicts = resolve_overlap(records, threshold=3, overrides=overrides)
    assert merged["labels"] == [{"start": 0, "end": 1, "label": "A"}]
    assert conflicts == []
