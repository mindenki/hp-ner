"""IOB2 reader and PyTorch Dataset for EWT NER.

The EWT IOB2 format is 5-column tab-separated with comment lines (starting with #) and blank-line sentence boundaries:

    # sent_id = ...
    1   Where   O       -   -
    6   Iguazu  B-LOC   -   stephen
    7   ?       O       -   -

Only columns 2 (token) and 3 (label) are used.
"""
import logging
from dataclasses import dataclass
from pathlib import Path

import torch
from torch.utils.data import Dataset
from transformers import PreTrainedTokenizerFast

logger = logging.getLogger(__name__)

IGNORED_LABEL_ID: int = -100


@dataclass
class Sentence:
    words: list[str]
    labels: list[str]


def read_iob2(path: Path) -> list[Sentence]:
    """Read an IOB2 file and return a list of Sentence objects.

    Supported variants (whitespace-separated):
    - 2 columns: TOKEN LABEL
    - 3 columns: IDX TOKEN LABEL
    - 5 columns (EWT): IDX TOKEN LABEL _ _

    Comment lines starting with ``#`` are skipped; blank lines separate sentences.
    """
    logger.info(f"Reading IOB2 file: {path}")
    sentences: list[Sentence] = []
    current_words: list[str] = []
    current_labels: list[str] = []

    with path.open(encoding="utf-8") as fh:
        for line in fh:
            raw = line.rstrip("\n")
            if raw.lstrip().startswith("#"):
                continue
            if raw.strip() == "":  # Sentence boundary
                if current_words:
                    sentences.append(Sentence(words=current_words, labels=current_labels))
                    current_words = []
                    current_labels = []
            else:
                parts = raw.split()
                word: str | None = None
                label: str | None = None
                if len(parts) >= 5:
                    # EWT-style: idx, token, label, _, _
                    word, label = parts[1], parts[2]
                elif len(parts) == 3:
                    # idx, token, label
                    word, label = parts[1], parts[2]
                elif len(parts) == 2:
                    # token, label
                    word, label = parts[0], parts[1]
                else:
                    logger.warning(
                        "Skipping malformed IOB2 line in %s: %r",
                        path.name,
                        raw,
                    )
                    continue

                current_words.append(word)
                current_labels.append(label)

    if current_words:
        sentences.append(Sentence(words=current_words, labels=current_labels))

    logger.info(f"Loaded {len(sentences)} sentences from {path.name}")
    return sentences


def build_label_vocab(sentences: list[Sentence]) -> tuple[dict[str, int], dict[int, str]]:
    """Build label2id / id2label from training sentences.

    - "O" is always id 0
    - remaining labels are sorted alphabetically for stability
    """
    unique_labels: set[str] = set()
    for sentence in sentences:
        unique_labels.update(sentence.labels)

    sorted_labels = ["O"] + sorted(_l for _l in unique_labels if _l != "O")
    label2id: dict[str, int] = {label: i for i, label in enumerate(sorted_labels)}
    id2label: dict[int, str] = {i: label for label, i in label2id.items()}
    logger.info(f"Built label vocabulary: {len(label2id)} labels — {list(label2id.keys())}")
    return label2id, id2label


class NERDataset(Dataset):
    """PyTorch Dataset for token classification with subword label alignment."""

    def __init__(self, sentences: list[Sentence], tokenizer: PreTrainedTokenizerFast, label2id: dict[str, int], max_length: int = 128) -> None:
        self.sentences = sentences
        self._tokenizer = tokenizer
        self._label2id = label2id
        self._max_length = max_length # Truncate long sentences to reduce memory usage
        logger.info(f"Tokenizing and aligning labels for {len(sentences)} sentences ...")
        self._items = [self._tokenize_and_align(s) for s in self.sentences]
        logger.info(f"Dataset ready — {len(self._items)} samples")

    def _tokenize_and_align(self, sentence: Sentence) -> dict[str, torch.Tensor]:
        """Tokenize a sentence and align original token labels to subword tokens.
        
        # Example sentence: ["Iguazu", "Falls", "are", "beautiful"]
        word_ids() example:
            position:  0      1     2     3    4        5      6           7
            subword:  [CLS]  ▁Ig  uaz    u   ▁Falls   ▁are  ▁beautiful  [SEP]
            word_id:  None    0    0     0     1        2       3         None

        Returns:
            # Model's vocabulary table maps "Iguazu" to id 5432
            "input_ids":      [1,    5432, 892, 29,  1876,   354,   2341,    2  ]
                               CLS    ▁Ig  uaz   u   ▁Falls  ▁are  ▁beaut.  SEP

            "attention_mask": [1,    1,    1,   1,   1,      1,     1,       1  ]

            "labels":         [-100, 1,   -100, -100, 2,      0,     0,    -100 ]
                               CLS  B-LOC  skip  skip I-LOC    O      O      SEP
        """
        logger.debug(f"Tokenizing sentence: {sentence.words}")
        encoding = self._tokenizer(
            sentence.words,
            is_split_into_words=True,
            truncation=True,
            max_length=self._max_length,
            padding=False,
            return_tensors="pt",
        )

        word_ids = encoding.word_ids(batch_index=0) # batch_index=0 means the only sentence in this encoding
        aligned_labels: list[int] = []
        previous_word_id: int | None = None

        for word_id in word_ids:
            if word_id is None:
                aligned_labels.append(IGNORED_LABEL_ID)
            elif word_id != previous_word_id:
                aligned_labels.append(self._label2id[sentence.labels[word_id]])
            else:
                aligned_labels.append(IGNORED_LABEL_ID)
            previous_word_id = word_id

        logger.debug(f"Aligned labels for sentence: {aligned_labels}")
        return {
            "input_ids": encoding["input_ids"].squeeze(0),
            "attention_mask": encoding["attention_mask"].squeeze(0),
            "labels": torch.tensor(aligned_labels, dtype=torch.long),
        }

    def __len__(self) -> int:
        """Return the number of sentences in the dataset."""
        return len(self._items)

    def __getitem__(self, idx: int) -> dict[str, torch.Tensor]:
        """Return the tokenized and aligned features for the sentence at index idx."""
        return self._items[idx]


def collate_fn(batch: list[dict[str, torch.Tensor]]) -> dict[str, torch.Tensor]:
    """Dynamically pad a batch of tokenized sentences and their aligned labels.
    
    Argument in pad_sequence:
        - batch_first=True: DeBERTa (and all HuggingFace models) expect input as [batch_size, seq_len]

    Returns:
        A dict with keys "input_ids", "attention_mask", and "labels", where each value is a padded tensor of shape [batch_size, max_seq_len].
    """
    logger.debug(f"Collating batch of {len(batch)} samples with varying sequence lengths ...")
    input_ids = torch.nn.utils.rnn.pad_sequence(
        [item["input_ids"] for item in batch],
        batch_first=True, # To have batch_size as the first dimension
        padding_value=0,
    )
    attention_mask = torch.nn.utils.rnn.pad_sequence(
        [item["attention_mask"] for item in batch],
        batch_first=True,
        padding_value=0,
    )
    labels = torch.nn.utils.rnn.pad_sequence(
        [item["labels"] for item in batch],
        batch_first=True,
        padding_value=IGNORED_LABEL_ID,
    )
    logger.debug(f"Batch collated — input_ids: {input_ids.shape}, attention_mask: {attention_mask.shape}, labels: {labels.shape}")
    return {"input_ids": input_ids, "attention_mask": attention_mask, "labels": labels}
