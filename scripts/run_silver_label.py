"""
S5 — Silver Labeling

Usage (from project root):
    python scripts/run_silver_label.py
    python scripts/run_silver_label.py --batch-size 64 --run run_20240101_120000

"""

import argparse
import json
import logging
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.silver_labeling.tokenizer import Tokenizer
from src.silver_labeling.entity_dict import EntityDictionary, matches_to_bio
from src.silver_labeling.bert_tagger import BertTagger
from src.silver_labeling.merger import merge, iob2_to_spans
from src.silver_labeling.stats import SilverStats

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("data/silver_label.log"),
    ],
)
logger = logging.getLogger(__name__)

LABEL_DISPLAY = {
    "CHAR": "Character",
    "LOC": "Location",
    "ORG": "Organization",
    "SPELL": "Spell",
    "CREA": "Creature",
    "ARTI": "Artifact",
}
def to_doccano_labels(tokens: list[str], tags: list[str], text: str) -> list[list]:
    """Convert IOB2 tags to Doccano character-offset format.
    Returns list of [start, end, label] spans.
    """
    
    spans = []
    i = 0
    char_pos = 0
    
    while i < len(tokens):
        token = tokens[i]
        
        
        start = text.index(token, char_pos) # token starts here
        end = start + len(token) # token ends here
        
        if tags[i].startswith("B-"):
            entity_type = tags[i][2:]
            span_start = start
            span_end = end
            
            # continue until the end of the entity
            
            j = i + 1
            while j < len(tokens) and tags[j] == f"I-{entity_type}":
                next_token = tokens[j]
                next_start = text.index(next_token, span_end) # next token starts after current span
                next_end = next_start + len(next_token)
                
                span_end = next_end
                j += 1
            label = LABEL_DISPLAY.get(entity_type, entity_type)
            spans.append([span_start, span_end, label])
            char_pos = span_end
            i = j
        else:
            char_pos = end
            i += 1
    return spans


def parse_args():
    p = argparse.ArgumentParser(description="S5 Silver Labeling")
    p.add_argument("--input", default="data/clean/wiki_data_filtered.jsonl")
    p.add_argument("--dicts-dir", default="data/dictionaries/txts")
    p.add_argument("--output", default="data/silver/hp_silver.jsonl")
    p.add_argument("--batch-size", type=int, default=32)
    p.add_argument("--max-length", type=int, default=128)
    p.add_argument(
        "--run", default=None, help="Run folder name. Defaults to LATEST_RUN.txt."
    )
    return p.parse_args()


def main():
    args = parse_args()

    # Load input sentences

    input_path = Path(args.input)
    if not input_path.exists():
        logger.error(f"Input file not found at {input_path}")
        return

    records = []
    with open(input_path, "r", encoding="utf-8") as f:
        for line in f:
            records.append(json.loads(line))
    logger.info(f"Loaded {len(records)} sentences from {input_path}")

    # Components

    tokenizer = Tokenizer()
    entity_dict = EntityDictionary(args.dicts_dir)
    bert_tagger = BertTagger(
        run_arg=args.run,
        batch_size=args.batch_size,
        max_length=args.max_length,
    )
    stats = SilverStats()

    # Tokenize sentences
    logger.info("Tokenizing sentences...")
    all_texts = [s["text"] for s in records]
    all_tokens = tokenizer.tokenize_batch(all_texts)

    # Bert tagging
    logger.info("Running BERT tagger...")
    all_bert_tags = bert_tagger.tag_batch(all_tokens)

    # Dict matching + merging

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    logger.info("Matching entities from dictionary and merging with BERT tags...")

    with open(output_path, "w", encoding="utf-8") as out_f:
        for idx, (record, tokens, bert_tags) in enumerate(
            zip(records, all_tokens, all_bert_tags)
        ):
            sentence_conflicts = defaultdict(int)

            dict_matches = entity_dict.match(tokens)
            dict_tags = matches_to_bio(tokens, dict_matches)

            merged_tags, sources, number_of_conflicts = merge(
                dict_tags=dict_tags,
                bert_tags=bert_tags,
                conflict_counts=sentence_conflicts,
            )

            spans = iob2_to_spans(merged_tags)
            entity_types = sorted(set(s for _, _, s in spans))
            entity_count = len(spans)

            stats.update(
                merged_tags, sources, entity_count, entity_types, sentence_conflicts
            )

            out_record = {
                "id": record["id"],
                "title": record["title"],
                "text": record["text"],
                "tokens": tokens,
                "silver_labels": merged_tags,
                "labels": to_doccano_labels(tokens, merged_tags, record["text"]),
                "entity_count": entity_count,
                "entity_types": entity_types,
                "silver_source": sources,
                "number_of_conflicts": number_of_conflicts,
            }

            out_f.write(json.dumps(out_record, ensure_ascii=False) + "\n")

    stats.log_summary()
    logger.info(f"Finished writing silver-labeled sentences to {output_path}")


if __name__ == "__main__":
    main()
