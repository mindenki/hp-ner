import json
import logging
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import torch
from seqeval.metrics import (
    accuracy_score,
    classification_report,
    f1_score,
    precision_score,
    recall_score,
)
from seqeval.scheme import IOB2
from torch.utils.data import DataLoader

from src.dataset import NERDataset, collate_fn
from src.model import DeBERTaNER
from src.plots import plot_confusion, plot_per_class

logger = logging.getLogger(__name__)


class Evaluator:
    """Runs inference and writes predictions in IOB2 format."""

    def __init__(self, model: DeBERTaNER, device: str, batch_size: int = 32) -> None:
        logger.info(f"Initializing Evaluator with device={device}, batch_size={batch_size}")
        self._model = model.model   # HuggingFace nn.Module — used for forward passes
        self._device = torch.device(device)
        self._batch_size = batch_size
        self._model.to(self._device)

    def predict(self, dataset: NERDataset) -> list[list[str]]:
        """Run inference and return predicted label sequences aligned to original tokens.

        Each returned sublist has exactly as many labels as the corresponding
        sentence has tokens (IGNORED positions from subword tokenization are removed).
        """
        id2label: dict[int, str] = self._model.config.id2label
        dataloader = DataLoader(
            dataset,
            batch_size=self._batch_size,
            shuffle=False,
            collate_fn=collate_fn,
        )

        logger.info(
            "Running inference on %d sentences (%d batches, batch_size=%d) ...",
            len(dataset.sentences), len(dataloader), self._batch_size,
        )

        all_predictions: list[list[str]] = []

        self._model.eval() # evaluation mode activated, autobots rollout!
        with torch.no_grad():
            for batch in dataloader:
                labels = batch["labels"]
                batch = {k: v.to(self._device) for k, v in batch.items()}
                outputs = self._model(**batch)
                # outputs.logits shape: (batch_size, seq_len, num_labels)
                # argmax(dim=-1) picks the index of the highest score along the last dimension
                # then collapses that dimension, resulting in shape: (batch_size, seq_len)
                predictions = outputs.logits.argmax(dim=-1).cpu()

                for pred_seq, label_seq in zip(predictions, labels):
                    sent_preds: list[str] = []
                    for p, _l in zip(pred_seq.tolist(), label_seq.tolist()): # convert to list from tensors
                        if _l == -100:
                            continue
                        sent_preds.append(id2label[p]) # convert predicted label ID to label string
                    all_predictions.append(sent_preds)

        # Verify alignment: each prediction list must match its sentence token count.
        # Truncation at max_length can shorten very long sentences; pad with "O" if needed.
        aligned: list[list[str]] = []
        truncated_count = 0
        for sentence, preds in zip(dataset.sentences, all_predictions):
            n = len(sentence.words)
            if len(preds) < n:
                truncated_count += 1
                preds = preds + ["O"] * (n - len(preds))
            aligned.append(preds[:n])

        if truncated_count:
            logger.warning(f"{truncated_count} sentence(s) were truncated at max_length and padded with 'O'")

        logger.info(f"Inference complete — {len(aligned)} sequences predicted")
        return aligned

    def write_predictions(self, dataset: NERDataset, predictions: list[list[str]], output_path: Path) -> None:
        """Write predictions in EWT tab-separated format compatible with span_f1.py.

        Format:
            - Each line is: token_index \t token \t predicted_label
            - Sentences are separated by blank lines.
        """
        logger.info(f"Writing predictions to: {output_path}")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        lines: list[str] = []
        for sentence, preds in zip(dataset.sentences, predictions):
            for i, (word, label) in enumerate(zip(sentence.words, preds), start=1):
                lines.append(f"{i}\t{word}\t{label}")
            lines.append("")
        output_path.write_text("\n".join(lines), encoding="utf-8")
        logger.info(f"Predictions written — {len(dataset.sentences)} sentences")

    def performance_metrics(
        self,
        gold: list[list[str]],
        pred: list[list[str]],
        output_dir: Path,
        model_name: str,
    ) -> dict[str, Any]:
        """Compute span-level metrics, append to metrics.jsonl, and write plots.

        Returns the metrics dict.

        Side effects:
          - appends one JSON line to ``output_dir / 'metrics.jsonl'``
          - writes ``output_dir / 'plots' / 'per_class.png'`` (overwrites existing)
          - writes ``output_dir / 'plots' / 'confusion.png'`` (overwrites existing)
        """
        if len(gold) != len(pred):
            raise ValueError(f"gold/pred length mismatch: {len(gold)} vs {len(pred)}")

        kwargs = {"mode": "strict", "scheme": IOB2, "zero_division": 0}
        overall = {
            "precision": float(precision_score(gold, pred, **kwargs)),
            "recall": float(recall_score(gold, pred, **kwargs)),
            "f1": float(f1_score(gold, pred, **kwargs)),
            "accuracy": float(accuracy_score(gold, pred)),
        }
        report = classification_report(gold, pred, output_dict=True, **kwargs)

        # Drop seqeval's synthetic aggregate rows (e.g., "micro avg", "macro avg", "weighted avg").
        per_class = {
            label: scores
            for label, scores in report.items()
            if isinstance(scores, dict) and not label.endswith(" avg")
        }

        record = {
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "model_name": model_name,
            "overall": overall,
            "per_class": per_class,
        }
        output_dir.mkdir(parents=True, exist_ok=True)
        metrics_path = output_dir / "metrics.jsonl"
        with metrics_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record) + "\n")
        logger.info(
            f"Appended metrics row to {metrics_path}  "
            f"P={overall['precision']:.4f}  R={overall['recall']:.4f}  "
            f"F1={overall['f1']:.4f}  acc={overall['accuracy']:.4f}",
        )

        plots_dir = output_dir / "plots"
        plot_per_class(per_class, plots_dir / "per_class.png", title=f"{model_name} — per-class metrics")

        labels, matrix = self._build_entity_confusion(gold, pred)
        plot_confusion(matrix, labels, plots_dir / "confusion.png", title=f"{model_name} — entity confusion")

        return record

    @staticmethod
    def _extract_spans(sequence: list[str]) -> list[tuple[int, int, str]]:
        """Extract (start, end_exclusive, label) entity spans from one IOB2 sequence."""
        spans: list[tuple[int, int, str]] = []
        start: int | None = None
        current_label: str | None = None

        def flush(end: int) -> None:
            if start is not None and current_label is not None:
                spans.append((start, end, current_label))

        for idx, tag in enumerate(sequence):
            if tag == "O" or "-" not in tag:
                flush(idx)
                start, current_label = None, None
                continue
            prefix, label = tag.split("-", 1)
            if prefix == "B" or label != current_label:
                flush(idx)
                start, current_label = idx, label
            # "I-" continuing the same label: nothing to do.
        flush(len(sequence))
        return spans

    @classmethod
    def _build_entity_confusion(
        cls,
        gold: list[list[str]],
        pred: list[list[str]],
    ) -> tuple[list[str], np.ndarray]:
        """Build an entity-level confusion matrix with MISS / SPURIOUS sentinels.

        - exact span+label match: increments ``(label, label)``
        - exact span, different label: increments ``(gold_label, pred_label)``
        - gold span without overlapping pred span: increments ``(gold_label, 'MISS')``
        - pred span without overlapping gold span: increments ``('SPURIOUS', pred_label)``
        """
        miss = "MISS"
        spurious = "SPURIOUS"
        class_labels: set[str] = set()
        pairs: list[tuple[str, str]] = []

        for gold_seq, pred_seq in zip(gold, pred):
            gold_spans = cls._extract_spans(gold_seq)
            pred_spans = cls._extract_spans(pred_seq)
            class_labels.update(label for _, _, label in gold_spans)
            class_labels.update(label for _, _, label in pred_spans)

            pred_by_range: dict[tuple[int, int], str] = {(s, e): label for s, e, label in pred_spans}
            gold_by_range: dict[tuple[int, int], str] = {(s, e): label for s, e, label in gold_spans}

            for (s, e), gold_label in gold_by_range.items():
                pred_label = pred_by_range.get((s, e))
                if pred_label is None:
                    pairs.append((gold_label, miss))
                else:
                    pairs.append((gold_label, pred_label))

            for (s, e), pred_label in pred_by_range.items():
                if (s, e) not in gold_by_range:
                    pairs.append((spurious, pred_label))

        labels = sorted(class_labels) + [miss, spurious]
        index = {label: i for i, label in enumerate(labels)}
        matrix = np.zeros((len(labels), len(labels)), dtype=int)
        for gold_label, pred_label in pairs:
            matrix[index[gold_label], index[pred_label]] += 1
        return labels, matrix

    def run_span_f1(self, gold_path: Path, pred_path: Path) -> None:
        """Call the course-provided span_f1.py if it exists at the project root."""
        # Resolve project root as two levels above this file (baseline/src/ -> project root)
        project_root = Path(__file__).resolve().parent.parent.parent
        span_f1_script = project_root / "span_f1.py"

        if not span_f1_script.exists():
            logger.warning(
                f"span_f1.py not found at {project_root} — skipping official span F1 evaluation"
            )
            return

        logger.info(f"Running span_f1.py: gold={gold_path.name}  pred={pred_path.name}")
        result = subprocess.run(
            [sys.executable, str(span_f1_script), str(gold_path), str(pred_path)],
            capture_output=True,
            text=True,
        )
        if result.stdout:
            logger.info("span_f1.py output:\n%s", result.stdout.strip())
        if result.returncode != 0:
            logger.error("span_f1.py exited with non-zero code: %d\n%s", result.returncode, result.stderr.strip())
