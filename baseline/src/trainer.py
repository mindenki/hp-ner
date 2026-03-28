import json
import logging
import random
from dataclasses import dataclass
from typing import Optional
from pathlib import Path

import numpy as np
import torch
from seqeval.metrics import f1_score
from torch.utils.data import DataLoader
from transformers import get_linear_schedule_with_warmup

from src.dataset import NERDataset, collate_fn
from src.model import DeBERTaNER

logger = logging.getLogger(__name__)


@dataclass
class TrainConfig:
    num_epochs: int = 5
    learning_rate: float = 5e-5
    batch_size: int = 16
    warmup_ratio: float = 0.1
    weight_decay: float = 0.01
    device: str = "cuda"
    seed: Optional[int | None] = None


class Trainer:
    """Manual PyTorch training loop for DeBERTaNER."""

    def __init__(self, model: DeBERTaNER, config: TrainConfig, output_dir: Path) -> None:
        logger.info(f"Initializing trainer with config: {config}")
        self._ner = model           # DeBERTaNER wrapper — used for save/load
        self._model = model.model   # HuggingFace nn.Module — used for forward passes
        self._config = config
        self._output_dir = output_dir
        self._history: list[dict] = []

    def train(self, train_dataset: NERDataset, dev_dataset: NERDataset) -> None:
        """Run the full training loop and save the best checkpoint."""
        self._set_seeds()

        device = self._resolve_device(self._config.device)
        logger.info("Moving model to device: %s", device)
        self._model.to(device)

        logger.info("Creating data loaders...")
        train_loader = DataLoader(
            train_dataset,
            batch_size=self._config.batch_size, # number of sentences per batch
            shuffle=True, # randomize order each epoch to improve generalization
            collate_fn=collate_fn,
        )
        dev_loader = DataLoader(
            dev_dataset,
            batch_size=self._config.batch_size * 2, # no backward pass, so we can safely double batch size
            shuffle=False, # order doesn't affect evaluation
            collate_fn=collate_fn,
        )

        logger.info("Building optimizer...")
        optimizer = self._build_optimizer()
        total_steps = len(train_loader) * self._config.num_epochs
        warmup_steps = int(total_steps * self._config.warmup_ratio)
        logger.info(f"Total training steps: {total_steps}  Warmup steps: {warmup_steps}")
        scheduler = get_linear_schedule_with_warmup(
            optimizer,
            num_warmup_steps=warmup_steps,
            num_training_steps=total_steps,
        )

        logger.info(
            f"Training started — device={device}  epochs={self._config.num_epochs}  batch_size={self._config.batch_size}  "
            f"lr={self._config.learning_rate:.2e}  total_steps={total_steps}  warmup_steps={warmup_steps}",
        )

        id2label = self._model.config.id2label
        best_f1 = 0.0

        for epoch in range(1, self._config.num_epochs + 1):
            train_loss = self._train_epoch(train_loader, optimizer, scheduler, device)
            dev_f1 = self._evaluate(dev_loader, id2label, device)

            logger.info(
                f"Epoch {epoch}/{self._config.num_epochs} — train_loss={train_loss:.4f}  dev_f1={dev_f1:.4f}",
            )

            self._history.append({"epoch": epoch, "train_loss": train_loss, "dev_f1": dev_f1})

            if dev_f1 > best_f1:
                best_f1 = dev_f1
                self._ner.save(self._output_dir / "best_model")
                logger.info(f"New best model saved (dev_f1={best_f1:.4f})")

        self._output_dir.mkdir(parents=True, exist_ok=True)
        history_path = self._output_dir / "training_history.json"
        history_path.write_text(json.dumps(self._history, indent=2), encoding="utf-8")
        logger.info(
            f"Training complete — best dev F1: {best_f1:.4f}  checkpoint: {self._output_dir / 'best_model'}  history: {history_path}",
        )

    def _train_epoch(self, dataloader: DataLoader, optimizer: torch.optim.Optimizer, scheduler, device: torch.device) -> float:
        """Train for one epoch and return average loss.

        Per-batch parameter update cycle:
          1. loss.backward()        — computes ∂loss/∂w for every parameter via
                                      backpropagation; each param gets a .grad tensor
          2. clip_grad_norm_()      — scales all gradients down proportionally if their
                                      global norm exceeds 1.0, preventing explosion.
          3. optimizer.step()       — AdamW updates each parameter in-place using its
                                      gradient, momentum, and adaptive LR estimates.
                                      The optimizer holds direct references to the model's
                                      tensors, so the model is updated immediately.
          4. scheduler.step()       — advances the LR schedule (linear warmup -> decay)
                                      for the next batch.
          5. optimizer.zero_grad()  — clears all .grad tensors so the next batch's
                                      gradients don't accumulate on top of these.
        """
        self._model.train() # switch model to training mode (enables dropout, etc.)
        total_loss = 0.0

        logger.debug(f"Training epoch with {len(dataloader)} batches ...")
        for batch_idx, batch in enumerate(dataloader):
            batch = {k: v.to(device) for k, v in batch.items()} # move batch tensors to 'device' as DataLoader returns CPU tensors by default

            outputs = self._model(**batch)
            logger.debug(f"Batch {batch_idx + 1}/{len(dataloader)} — raw loss: {outputs.loss.item():.4f}")
            loss = outputs.loss
            logger.debug(f"Batch {batch_idx + 1}/{len(dataloader)} — loss after scaling: {loss.item():.4f}")
            loss.backward()
            grad_norm = torch.nn.utils.clip_grad_norm_(self._model.parameters(), max_norm=1.0) # scale all gradients down proportionally if that norm exceeds 1.0
            optimizer.step()
            logger.debug(f"Batch {batch_idx + 1}/{len(dataloader)} — optimizer step completed  grad_norm={grad_norm:.4f}")
            scheduler.step() # update learning rate
            optimizer.zero_grad()
            total_loss += loss.item()

            if (batch_idx + 1) % 50 == 0:
                logger.debug(f"  batch {batch_idx + 1}/{len(dataloader)} — loss={loss.item():.4f}  lr={scheduler.get_last_lr()[0]:.2e}")

        return total_loss / len(dataloader) # average loss per batch

    def _evaluate(self, dataloader: DataLoader, id2label: dict[int, str], device: torch.device) -> float:
        """Evaluate on the dev set and return micro-averaged F1 score."""
        logger.debug(f"Running evaluation on dev set ({len(dataloader)} batches) ...")
        self._model.eval() # turn the switch to evaluation mode (disables dropout, etc.)
        # we store the true and predicted sequences for F1 calculation
        true_sequences: list[list[str]] = []
        pred_sequences: list[list[str]] = []

        with torch.no_grad():
            for batch in dataloader:
                labels = batch["labels"]
                batch = {k: v.to(device) for k, v in batch.items()} # move batch tensors to 'device'
                outputs = self._model(**batch) # based on the input batch, we get a prediction for all tokens
                predictions = outputs.logits.argmax(dim=-1).cpu() # for each token, we predict the label with the highest logit score
                logger.debug(f"Batch evaluation — predictions shape: {predictions.shape}  labels shape: {labels.shape}")
                for pred_seq, label_seq in zip(predictions, labels): # iterate over each sentence in the batch
                    true_sent: list[str] = []
                    pred_sent: list[str] = []
                    for p, _l in zip(pred_seq.tolist(), label_seq.tolist()): # iterate over each token in the sentence
                        if _l == -100: # ignore special tokens
                            continue
                        # append the predicted and true labels for this token
                        true_sent.append(id2label[_l])
                        pred_sent.append(id2label[p])
                    # after processing all tokens in the sentence, we have the full sequence of true and predicted labels for that sentence
                    true_sequences.append(true_sent)
                    pred_sequences.append(pred_sent)
        logger.debug(f"Evaluation complete — total sentences: {len(true_sequences)}")
        return f1_score(true_sequences, pred_sequences, average="micro", zero_division=0)

    def _build_optimizer(self) -> torch.optim.AdamW:
        """Set up AdamW optimizer with separate weight decay for bias and LayerNorm parameters."""
        no_decay = {"bias", "LayerNorm.weight"}
        decay_params, no_decay_params = [], []

        for name, param in self._model.named_parameters():
            if any(nd in name for nd in no_decay):
                no_decay_params.append(param)
            else:
                decay_params.append(param)

        logger.debug(f"Optimizer parameter groups — with decay: {len(decay_params)}  without decay: {len(no_decay_params)}")

        param_groups = [
            {"params": decay_params,    "weight_decay": self._config.weight_decay},
            {"params": no_decay_params, "weight_decay": 0.0},
        ]
        return torch.optim.AdamW(param_groups, lr=self._config.learning_rate)

    def _set_seeds(self) -> None:
        """Set random seeds for reproducibility."""
        logger.debug(f"Setting random seeds to {self._config.seed}")
        random.seed(self._config.seed)
        np.random.seed(self._config.seed)
        torch.manual_seed(self._config.seed)
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(self._config.seed)

    @staticmethod
    def _resolve_device(device_name: str) -> torch.device:
        """Resolve a requested device string to a safe torch.device.

        Behavior:
        - "cpu" -> CPU
        - "cuda", "cuda:0", ... -> CUDA if available, otherwise fallback to CPU
        - "auto" -> CUDA if available, otherwise CPU
        """
        requested = (device_name or "auto").strip().lower()

        if requested == "auto":
            return torch.device("cuda" if torch.cuda.is_available() else "cpu")

        if requested.startswith("cuda"):
            if not torch.cuda.is_available():
                logger.warning(
                    "CUDA was requested but this PyTorch build has no CUDA support or no GPU is available. "
                    "Falling back to CPU.",
                )
                return torch.device("cpu")
            return torch.device(requested)

        return torch.device(requested)
