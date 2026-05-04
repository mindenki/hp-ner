"""
BERT Tagger for silver labeling.

Loads in the fine-tuned baseline DeBertaV3 model and runs inference on pre-tokenized text(tokenized usings tokenizer.py).


EWT label set (PER/LOC/ORG) is mapped to HP Label set(CHAR/LOC/ORG). 
The model cannot predict CREATURE, ARTIFACT, or SPELL, so those are always labeled as O (non-entity).

"""


import logging
import json, sys
from pathlib import Path


import torch

from baseline.src.model import DeBERTaNER


logger = logging.getLogger(__name__)


BERT_LABEL_MAP = {
    "B-PER": "B-CHAR", "I-PER": "I-CHAR",
    "B-LOC": "B-LOC", "I-LOC": "I-LOC",
    "B-ORG": "B-ORG", "I-ORG": "I-ORG",
    "O": "O"}




def _resolve_run_dir(run_arg: str | None) -> tuple[Path, Path]:
    """
    Returns (best_model_path, label2id_path) for the requested
    (or latest) run.
    """
    base = Path("outputs/baseline")

    if run_arg:
        run_dir = base / run_arg
    else:
        latest_file = base / "LATEST_RUN.txt"
        if not latest_file.exists():
            raise FileNotFoundError(f"No LATEST_RUN.txt at {latest_file}")
        run_dir = base / latest_file.read_text(encoding="utf-8").strip()

    best_model = run_dir / "best_model"
    label2id_path = run_dir / "label2id.json"

    if not best_model.exists():
        raise FileNotFoundError(f"best_model not found at {best_model}")
    if not label2id_path.exists():
        raise FileNotFoundError(f"label2id.json not found at {label2id_path}")

    return best_model, label2id_path

    

class BertTagger:
    """ 
    Wraps the fine tuned DeBertaV3 model for silver labeling.
    
    Takes pre-tokenized token lists (is_split_into_words=True),
    runs the DeBERTa tokenizer internally, aligns subword predictions
    back to word level, and returns HP-mapped IOB2 tags.
    """
    
    def __init__(self, run_arg: str | None = None, batch_size: int = 32, max_length: int = 128, device: torch.device | None = None):
        
        best_model_path, label2id_path = _resolve_run_dir(run_arg)
        
        self.label2id = json.loads(label2id_path.read_text(encoding="utf-8"))
        self.id2label = {v: k for k, v in self.label2id.items()}
        self.model = DeBERTaNER.load(best_model_path)
        self.device = device or torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.model.model.to(self.device)
        self.model.model.eval()
        
        self.batch_size = batch_size
        self.max_length = max_length
        
        logger.info(f"Loaded model from {best_model_path} with labels: {self.label2id}")
    
    
    def _predict_batch(self, batch_tokens: list[list[str]]) -> list[list[str]]:
        """ 
        Runs inference on one batch of pre-tokenized sentences and returns HP-mapped IOB2 tag lists, one per sentence.
        """
        
        encoding = self.model.tokenizer(
            batch_tokens,
            is_split_into_words=True,
            padding=True,
            truncation=True,
            max_length=self.max_length,
            return_tensors="pt",
        )
        
        input_ids = encoding["input_ids"].to(self.device)
        attention_mask = encoding["attention_mask"].to(self.device)
        token_type_ids = encoding.get("token_type_ids")
        if token_type_ids is not None:
            token_type_ids = token_type_ids.to(self.device)

        with torch.no_grad():
            outputs = self.model.model(input_ids = input_ids, attention_mask = attention_mask, token_type_ids = token_type_ids)
        
        
        predictions = torch.argmax(outputs.logits, dim=-1).cpu().tolist()
        
        results = []
        for i, tokens in enumerate(batch_tokens):
            word_ids = encoding.word_ids(batch_index=i)
            seen_word_ids = set()
            word_tags = {}
            
            for subword_idx, word_id in enumerate(word_ids):
                
                if word_id is None:
                    continue
                if word_id in seen_word_ids:
                    continue
                seen_word_ids.add(word_id)
                
                raw_label = self.id2label.get(predictions[i][subword_idx], "O")
                hp_label = BERT_LABEL_MAP.get(raw_label, "O")
                word_tags[word_id] = hp_label
                
            tags = [word_tags.get(w, "O") for w in range(len(tokens))]
            results.append(tags)
            
        return results
    
    def tag_batch(self, all_tokens: list[list[str]]) -> list[list[str]]:
        """ 
        Tag all sentences in minibatches, 
        Returns a list of IOB2 tag lists, one per sentence, aligned with the input tokens.
        """
        
        
        all_tags = []
        total = len(all_tokens)
        
        for i in range(0, total, self.batch_size):
            batch = all_tokens[i:i+self.batch_size]
            all_tags.extend(self._predict_batch(batch)) # extend since _predict_batch returns a list of tag lists, one per sentence in the batch
            
            if (i // self.batch_size) % 10 == 0:
                logger.info(f"Tagged {min(i+self.batch_size, total)}/{total} sentences...")
        
        
        return all_tags