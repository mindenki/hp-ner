from pathlib import Path
import pytest
from src.common.iob2 import Sentence, read_iob2, write_iob2

FIXTURES = Path(__file__).parent / "fixtures"


def test_read_generic_two_column():
    sentences = read_iob2(FIXTURES / "tiny.iob2")
    assert len(sentences) == 12
    assert sentences[0].words == ["Harry", "went", "to", "Hogwarts", "."]
    assert sentences[0].labels == ["B-CHAR", "O", "O", "B-LOC", "O"]
    assert sentences[1].words == ["Hermione", "cast", "Expelliarmus", "."]
    assert sentences[1].labels == ["B-CHAR", "O", "B-SPELL", "O"]


def test_read_ewt_five_column_skips_comments():
    sentences = read_iob2(FIXTURES / "tiny_ewt.iob2")
    assert len(sentences) == 2
    assert sentences[0].words == ["Where", "is", "Iguazu", "?"]
    assert sentences[0].labels == ["O", "O", "B-LOC", "O"]


def test_validate_rejects_orphan_i_label(tmp_path):
    bad = tmp_path / "bad.iob2"
    bad.write_text("Harry\tI-CHAR\n", encoding="utf-8")
    with pytest.raises(ValueError, match="Invalid IOB2 transition"):
        read_iob2(bad, validate=True)


def test_roundtrip_ewt_columns(tmp_path):
    sentences = read_iob2(FIXTURES / "tiny.iob2")
    out = tmp_path / "out.iob2"
    write_iob2(sentences, out, ewt_columns=True)
    reread = read_iob2(out)
    for orig, new in zip(sentences, reread):
        assert orig.words == new.words
        assert orig.labels == new.labels


def test_roundtrip_two_columns(tmp_path):
    sentences = read_iob2(FIXTURES / "tiny.iob2")
    out = tmp_path / "out.iob2"
    write_iob2(sentences, out, ewt_columns=False)
    reread = read_iob2(out)
    assert [(s.words, s.labels) for s in sentences] == [(s.words, s.labels) for s in reread]
