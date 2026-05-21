"""Dictionary-builder orchestration: crawl categories -> clean -> aliases -> .txt files.

One entry point called from ``scripts/prepare_annotation.py::_step_build_dict``.
"""
import json
import logging
from pathlib import Path

from src.dict_builder.alias_extractor import scrape_all_labels
from src.dict_builder.categories import CATEGORIES
from src.dict_builder.category_cleaner import clean_all
from src.dict_builder.category_crawler import crawl_all
from src.dict_builder.txt_writer import write_all_dicts

logger = logging.getLogger(__name__)


def build_dict_entrypoint(output_dir: Path) -> None:
    """Build the per-label entity dictionaries under ``output_dir``.

    Writes:
        <output_dir>/hp_raw.json
        <output_dir>/hp_canonical.json
        <output_dir>/hp_aliases.json
        <output_dir>/txts/{CHAR,LOC,ORG,SPELL,CREA,ARTI}.txt
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    raw_path = output_dir / "hp_raw.json"
    canonical_path = output_dir / "hp_canonical.json"
    txts_dir = output_dir / "txts"

    if raw_path.exists():
        logger.info("build_dict_entrypoint: reusing existing raw crawl at %s", raw_path)
        raw = json.loads(raw_path.read_text(encoding="utf-8"))
    else:
        logger.info("build_dict_entrypoint: crawling categories…")
        raw = crawl_all(CATEGORIES)
        raw_path.write_text(json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8")

    logger.info("build_dict_entrypoint: cleaning canonical entity names…")
    canonical = clean_all(raw)
    canonical_path.write_text(
        json.dumps(canonical, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    for label, entities in canonical.items():
        logger.info("  %s: %d entities", label, len(entities))

    logger.info("build_dict_entrypoint: scraping aliases…")
    aliases = scrape_all_labels(canonical)  # writes data/dictionaries/hp_aliases.json internally

    logger.info("build_dict_entrypoint: writing per-label .txt files to %s", txts_dir)
    write_all_dicts(canonical, aliases, txts_dir)
    logger.info("build_dict_entrypoint: done")
