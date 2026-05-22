import shutil
import subprocess
from pathlib import Path

FIXTURES = Path(__file__).parent / "fixtures" / "annotated"
ROOT = Path(__file__).resolve().parents[1]


def test_finalize_gold_produces_iob2(tmp_path):
    annotated = tmp_path / "data" / "annotated"
    annotated.mkdir(parents=True)
    for f in FIXTURES.iterdir():
        shutil.copy2(f, annotated / f.name)

    silver = tmp_path / "data" / "silver"
    silver.mkdir(parents=True)
    (silver / "hp_silver.jsonl").write_text(
        '{"tokens": ["Harry"], "labels": ["B-CHAR"], "text": "Harry"}\n',
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            "uv", "run", "python",
            str(ROOT / "scripts" / "finalize_gold.py"),
            "--only-step", "compute_iaa",
            "--only-step", "merge_gold",
            "--only-step", "write_iob2",
            "--non-interactive",
            "--allow-low-agreement",
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"STDOUT: {result.stdout}\nSTDERR: {result.stderr}"
    assert (tmp_path / "data" / "iaa" / "agreement.json").exists()
    assert (tmp_path / "data" / "selected" / "silver" / "silver.iob2").exists()
    assert (tmp_path / "data" / "selected" / "gold" / "gold.iob2").exists()
