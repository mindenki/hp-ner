import pytest
from src.common.iob2 import Sentence
from src.common.spans import (
    DOCCANO_TO_IOB2,
    IOB2_TO_DOCCANO,
    doccano_record_to_sentence,
    iob2_to_doccano_spans,
    spans_to_iob2,
    token_offsets,
)


def test_label_maps_are_inverses_of_each_other():
    assert IOB2_TO_DOCCANO == {v: k for k, v in DOCCANO_TO_IOB2.items()}
    assert set(IOB2_TO_DOCCANO.keys()) == {"CHAR", "LOC", "ORG", "CREA", "SPELL", "ARTI"}


def test_iob2_to_doccano_spans_single_token():
    text = "Harry went home"
    tokens = text.split()
    tags = ["B-CHAR", "O", "O"]
    spans = iob2_to_doccano_spans(tokens, text, tags, label_map=IOB2_TO_DOCCANO)
    assert spans == [[0, 5, "Character"]]


def test_iob2_to_doccano_spans_multi_token():
    text = "Lord Voldemort attacked Hogwarts"
    tokens = text.split()
    tags = ["B-CHAR", "I-CHAR", "O", "B-LOC"]
    spans = iob2_to_doccano_spans(tokens, text, tags, label_map=IOB2_TO_DOCCANO)
    assert spans == [[0, 14, "Character"], [24, 32, "Location"]]


def test_iob2_to_doccano_spans_is_inverse_of_doccano_record():
    """Round-trip: Doccano record -> Sentence -> back to Doccano-style spans."""
    text = "Harry cast Expelliarmus"
    record = {
        "text": text,
        "labels": [
            {"start": 0, "end": 5, "label": "Character"},
            {"start": 11, "end": 23, "label": "Spell"},
        ],
    }
    s = doccano_record_to_sentence(record, label_map=DOCCANO_TO_IOB2)
    roundtrip = iob2_to_doccano_spans(s.words, text, s.labels, label_map=IOB2_TO_DOCCANO)
    assert roundtrip == [[0, 5, "Character"], [11, 23, "Spell"]]


def test_token_offsets_for_whitespace_tokens():
    text = "Harry went to Hogwarts"
    tokens = text.split()
    offs = token_offsets(text, tokens)
    assert offs == [(0, 5), (6, 10), (11, 13), (14, 22)]


def test_token_offsets_handles_repeated_token():
    text = "the the cat"
    tokens = text.split()
    offs = token_offsets(text, tokens)
    assert offs == [(0, 3), (4, 7), (8, 11)]


def test_spans_to_iob2_single_token_span():
    text = "Harry went home"
    tokens = text.split()
    labels = spans_to_iob2(tokens, text, [(0, 5, "CHAR")])
    assert labels == ["B-CHAR", "O", "O"]


def test_spans_to_iob2_multi_token_span():
    text = "Lord Voldemort attacked"
    tokens = text.split()
    labels = spans_to_iob2(tokens, text, [(0, 14, "CHAR")])
    assert labels == ["B-CHAR", "I-CHAR", "O"]


def test_doccano_record_to_sentence_with_label_map():
    record = {
        "text": "Harry cast Expelliarmus",
        "labels": [
            {"start": 0, "end": 5, "label": "Character"},
            {"start": 11, "end": 23, "label": "Spell"},
        ],
    }
    label_map = {"Character": "CHAR", "Spell": "SPELL"}
    s = doccano_record_to_sentence(record, label_map=label_map)
    assert isinstance(s, Sentence)
    assert s.words == ["Harry", "cast", "Expelliarmus"]
    assert s.labels == ["B-CHAR", "O", "B-SPELL"]


def test_doccano_record_accepts_legacy_label_field_name():
    record = {
        "text": "Harry",
        "label": [[0, 5, "Character"]],
    }
    s = doccano_record_to_sentence(record, label_map={"Character": "CHAR"})
    assert s.labels == ["B-CHAR"]
