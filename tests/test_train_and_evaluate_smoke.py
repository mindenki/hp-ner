import shutil
import subprocess
import yaml
from pathlib import Path

FIXTURES = Path(__file__).parent / "fixtures"
ROOT = Path(__file__).resolve().parents[1]


def test_split_and_single_pipeline(tmp_path):
    gold_dir = tmp_path / "data" / "selected" / "gold"
    gold_dir.mkdir(parents=True)
    shutil.copy2(FIXTURES / "tiny.iob2", gold_dir / "gold.iob2")

    silver_dir = tmp_path / "data" / "selected" / "silver"
    silver_dir.mkdir(parents=True)
    shutil.copy2(FIXTURES / "tiny.iob2", silver_dir / "silver.iob2")

    tiny_cfg = {
        "model": {"name": "microsoft/deberta-v3-base", "max_length": 32},
        "paths": {
            "silver": "data/selected/silver/silver.iob2",
            "gold_train": "data/selected/gold/train.iob2",
            "gold_dev": "data/selected/gold/dev.iob2",
            "gold_test": "data/selected/gold/test.iob2",
            "ewt_checkpoint": "outputs/baseline/best_model",
            "output_root": "outputs/pipelines",
        },
        "training": {
            "num_epochs": 1, "learning_rate": 5e-5, "batch_size": 2,
            "warmup_ratio": 0.0, "weight_decay": 0.0, "device": "cpu", "seed": 42,
        },
        "evaluation": {"batch_size": 2},
        "pipelines": [
            {"name": "gold_from_base", "init_from": "base", "stages": [{"data": "gold_train"}]},
        ],
    }
    cfg_path = tmp_path / "tiny_pipelines.yaml"
    cfg_path.write_text(yaml.safe_dump(tiny_cfg), encoding="utf-8")

    result = subprocess.run(
        [
            "uv", "run", "python",
            str(ROOT / "scripts" / "train_and_evaluate.py"),
            "--pipelines-config", str(cfg_path),
            "--only-step", "split_gold",
            "--only-step", "run_pipelines",
            "--only-pipeline", "gold_from_base",
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=600,  # tiny but DeBERTa still has to load
    )
    assert result.returncode == 0, f"STDOUT: {result.stdout}\nSTDERR: {result.stderr}"
    assert (gold_dir / "train.iob2").exists()
    assert (gold_dir / "dev.iob2").exists()
    assert (gold_dir / "test.iob2").exists()
    runs = list((tmp_path / "outputs" / "pipelines" / "gold_from_base").glob("run_*"))
    assert runs, "no pipeline run dir created"
