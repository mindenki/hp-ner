import logging

from src.common.logging import setup_logging


def test_setup_logging_creates_log_file_and_appends(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    setup_logging("smoke")
    logger = logging.getLogger("src.smoke_check")
    logger.warning("first call")

    # Re-invoke — should append, not truncate, and not duplicate handlers
    setup_logging("smoke")
    logger.warning("second call")

    log_path = tmp_path / "outputs" / "logs" / "smoke.log"
    assert log_path.exists()
    content = log_path.read_text(encoding="utf-8")
    assert "first call" in content
    assert "second call" in content
    root_handlers = [h for h in logging.getLogger().handlers
                     if getattr(h, "_hp_ner_marker", False)]
    assert len(root_handlers) == 2  # console + file
