import logging
import subprocess
import sys
from pathlib import Path

import torch
from torch.utils.data import DataLoader

from src.dataset import NERDataset, collate_fn
from src.model import DeBERTaNER
from src.preprocessing.iob2 import IOB2Writer, Sentence

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
        pred_sentences = [
            Sentence(s.words, preds)
            for s, preds in zip(dataset.sentences, predictions)
        ]
        IOB2Writer(mode="ewt").write(pred_sentences, output_path)
        logger.info(f"Predictions written — {len(pred_sentences)} sentences")

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
