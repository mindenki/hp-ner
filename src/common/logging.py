"""Single logging configuration for all orchestrator scripts.

Writes to:
  - stderr at INFO+ (human-readable)
  - outputs/logs/<script_name>.log at DEBUG+ (append-only, full format)
"""
import logging
import sys
from pathlib import Path

_CONSOLE_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
_FILE_FORMAT = (
    "%(asctime)s | %(levelname)-8s | %(name)s | %(filename)s:%(lineno)d | %(message)s"
)
_DATEFMT = "%Y-%m-%d %H:%M:%S"


def setup_logging(script_name: str, *, level: int = logging.INFO) -> None:
    """Idempotent setup. Safe to call multiple times in one process."""
    root = logging.getLogger()

    if any(getattr(h, "_hp_ner_marker", False) for h in root.handlers):
        return

    root.setLevel(logging.DEBUG)

    console = logging.StreamHandler(sys.stderr)
    console.setLevel(level)
    console.setFormatter(logging.Formatter(_CONSOLE_FORMAT, datefmt=_DATEFMT))
    console._hp_ner_marker = True  # type: ignore[attr-defined]
    root.addHandler(console)

    log_dir = Path("outputs") / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    file_handler = logging.FileHandler(log_dir / f"{script_name}.log", mode="a", encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(_FILE_FORMAT, datefmt=_DATEFMT))
    file_handler._hp_ner_marker = True  # type: ignore[attr-defined]
    root.addHandler(file_handler)
