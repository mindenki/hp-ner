"""Silver-labelling orchestration: tokenize -> dict-match + BERT-tag -> merge -> write.

Called from ``scripts/prepare_annotation.py::_step_silver_label`` as a one-liner.
The low-level building blocks live in this package (`tokenizer`, `entity_dict`,
`bert_tagger`, `merger`, `stats`); this file glues them together.
"""
import json
import logging
from collections import defaultdict
from pathlib import Path

from src.common.spans import IOB2_TO_DOCCANO, iob2_to_doccano_spans
from src.silver_labeling.entity_dict import EntityDictionary, matches_to_bio
from src.silver_labeling.merger import iob2_to_spans, merge
from src.silver_labeling.stats import SilverStats
from src.silver_labeling.tokenizer import Tokenizer

logger = logging.getLogger(__name__)


def silver_label_entrypoint(
    input_path: Path,
    output_path: Path,
    dictionary_dir: Path,
    *,
    ewt_run: str | None = None,
) -> None:
    """Read filtered sentences, apply dict + BERT tagging, write silver JSONL.

    Falls back to dict-only tagging (BERT tags all ``O``) when no EWT checkpoint
    is available — useful for smoke tests and dictionary-only experiments.
    """
    records = [json.loads(line) for line in input_path.read_text(encoding="utf-8").splitlines() if line]
    logger.info("silver_label: loaded %d sentences from %s", len(records), input_path)

    tokenizer = Tokenizer()
    entity_dict = EntityDictionary(str(dictionary_dir))
    stats = SilverStats()

    all_tokens = tokenizer.tokenize_batch([r["text"] for r in records])

    bert_tagger = None
    try:
        from src.silver_labeling.bert_tagger import BertTagger
        bert_tagger = BertTagger(run_arg=ewt_run, batch_size=32, max_length=128)
        logger.info("silver_label: BertTagger loaded")
    except Exception as exc:  # noqa: BLE001 — any load failure should fall back
        logger.warning("silver_label: BertTagger unavailable (%s); dict-only tagging", exc)

    if bert_tagger is not None:
        all_bert_tags = bert_tagger.tag_batch(all_tokens)
    else:
        all_bert_tags = [["O"] * len(toks) for toks in all_tokens]

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as out_f:
        for record, tokens, bert_tags in zip(records, all_tokens, all_bert_tags):
            sentence_conflicts: dict = defaultdict(int)
            dict_tags = matches_to_bio(tokens, entity_dict.match(tokens))
            merged_tags, sources, n_conflicts = merge(
                dict_tags=dict_tags,
                bert_tags=bert_tags,
                conflict_counts=sentence_conflicts,
            )
            spans = iob2_to_spans(merged_tags)
            entity_types = sorted({s for _, _, s in spans})
            stats.update(merged_tags, sources, len(spans), entity_types, sentence_conflicts)

            out_record = {
                "id": record["id"],
                "title": record["title"],
                "text": record["text"],
                "tokens": tokens,
                "silver_labels": merged_tags,
                "labels": iob2_to_doccano_spans(
                    tokens, record["text"], merged_tags, label_map=IOB2_TO_DOCCANO,
                ),
                "entity_count": len(spans),
                "entity_types": entity_types,
                "silver_source": sources,
                "number_of_conflicts": n_conflicts,
            }
            out_f.write(json.dumps(out_record, ensure_ascii=False) + "\n")

    stats.log_summary()
    logger.info("silver_label: wrote silver-labelled sentences to %s", output_path)
