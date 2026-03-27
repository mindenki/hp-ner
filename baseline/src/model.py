from __future__ import annotations
from pathlib import Path

from transformers import AutoModelForTokenClassification, AutoTokenizer, PreTrainedTokenizerFast


class DeBERTaNER:
    """Wraps DeBERTaV3 with a token classification head sized for the target label set."""

    def __init__(self, model_name: str, num_labels: int, id2label: dict[int, str], label2id: dict[str, int]) -> None:
        """
            Tokenizer: downloads and loads tokenizer for 'model_name' from HuggingFace. This converts "Iguazu" to [5432, 892, 29]
            Model: downloads the pretrained 'model_name' weights
        """
        self.tokenizer: PreTrainedTokenizerFast = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModelForTokenClassification.from_pretrained(
            model_name=model_name,
            num_labels=num_labels, # number of output classes for the token classification head
            id2label=id2label,
            label2id=label2id,
            ignore_mismatched_sizes=True, # allows loading pretrained weights even if the classification head size doesn't match the pretrained model's original head size
        )

    def save(self, path: Path) -> None:
        """Save model weights and tokenizer to path.
        
        model.save_pretrained:
            - model.safetensors: all learned weights
            - config.json: architecture, id2label, label2id

        tokenizer.save_pretrained:
            - tokenizer.json: full SentencePiece vocab and tokenization rules
            - tokenizer_config.json: tokenizer class name and settings
            - special_tokens_map.json: mapping of special tokens (e.g. [CLS], [SEP]) to their IDs
        """
        path.mkdir(parents=True, exist_ok=True)
        self.model.save_pretrained(str(path))
        self.tokenizer.save_pretrained(str(path))

    @classmethod
    def load(cls, path: Path) -> DeBERTaNER:
        """Load a previously saved checkpoint."""
        instance = cls.__new__(cls) # creates a blank instance without calling __init__
        instance.tokenizer = AutoTokenizer.from_pretrained(str(path))
        instance.model = AutoModelForTokenClassification.from_pretrained(str(path))
        return instance
