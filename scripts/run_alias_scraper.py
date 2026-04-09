"""
Scrape aliases for canconcial entity names.


"""

import json
import logging
from pathlib import Path

from src.dict_builder.alias_extractor import scrape_all_labels

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("data/alias_scraper.log"),
    ]
)
logger = logging.getLogger(__name__)

def main():
    canonical_path = Path("data/dictionaries/hp_canonical.json")
    if not canonical_path.exists():
        logger.error(f"Canonical dictionary not found at {canonical_path}. Please run the category crawler first.")
        return

    
    canonical = json.loads(canonical_path.read_text(encoding="utf-8"))
    logger.info("Loaded canonical dictionary, starting alias scraping...")
    
    scrape_all_labels(canonical)
    logger.info("Alias scraping completed.")
    
    
    
if __name__ == "__main__":
    main()