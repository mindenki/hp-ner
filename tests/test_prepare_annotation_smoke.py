"""Smoke test for scripts/prepare_annotation.py — runs clean,
silver_label, select_15k via --only-step on the bundled raw fixture.
Doccano, EWT training, scraping, and dict build are skipped via
idempotency (we pre-populate their outputs)."""
import shutil
import subprocess
from pathlib import Path

FIXTURES = Path(__file__).parent / "fixtures"
ROOT = Path(__file__).resolve().parents[1]


def test_orchestrator_runs_listed_steps_only(tmp_path):
    # Working tree for the test
    (tmp_path / "data" / "raw").mkdir(parents=True)
    shutil.copy2(FIXTURES / "raw_tiny.jsonl",
                 tmp_path / "data" / "raw" / "wiki_data.jsonl")

    # Pre-populate dictionary txts so build_dict's idempotency check skips it.
    dict_dir = tmp_path / "data" / "dictionaries" / "txts"
    dict_dir.mkdir(parents=True)
    for fname in ("character", "location", "organization",
                  "spell", "creature", "artifact"):
        src = FIXTURES / "dictionaries" / f"{fname}.txt"
        dst = dict_dir / f"{fname}.txt"
        if src.exists():
            shutil.copy2(src, dst)
        else:
            dst.write_text("", encoding="utf-8")

    # Pre-populate an EWT-baseline checkpoint placeholder so train_ewt skips.
    ckpt = tmp_path / "outputs" / "baseline" / "run_smoke" / "best_model"
    ckpt.mkdir(parents=True)
    (ckpt / "config.json").write_text("{}", encoding="utf-8")

    result = subprocess.run(
        [
            "uv", "run", "python",
            str(ROOT / "scripts" / "prepare_annotation.py"),
            "--only-step", "clean",
            "--only-step", "silver_label",
            "--only-step", "select_15k",
            "--config", str(ROOT / "configs" / "baseline.yaml"),
            "--skip-doccano",
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"STDOUT: {result.stdout}\nSTDERR: {result.stderr}"
    assert (tmp_path / "data" / "filtered").exists()
    assert (tmp_path / "data" / "silver" / "hp_silver.jsonl").exists()
