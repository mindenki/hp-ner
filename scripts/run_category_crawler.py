"""
Crawl HP Fandom wiki categories and produce clean canonical entity lists.


Output: 
        {
            "CHAR": ["Severus Snape", "Bellatrix Lestrange", ...],
            
            "LOC": ["Hogwarts", "Diagon Alley", ...],
            
            etc.
              
        }
        
"""


import json
import logging
from pathlib import Path


from src.dict_builder.categories import CATEGORIES
from src.dict_builder.category_crawler import crawl_all
from src.dict_builder.category_cleaner import clean_all

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),                          # prints to terminal
        logging.FileHandler("data/crawler.log"),          # saves to file
    ]
)
logger = logging.getLogger(__name__)

logger.setLevel(logging.INFO)


def main():
    # STEP 1: CRAWLING CATEGORIES
    logger.info("#1 Starting category crawl...")
    raw_path = Path("data/dictionaries/hp_raw.json")

    if raw_path.exists():
        logger.info(f"Found existing raw crawl at {raw_path}, skipping crawl...")
        raw = json.loads(raw_path.read_text(encoding="utf-8"))
    else:
        logger.info("No existing raw crawl found, starting crawl...")
        raw = crawl_all(CATEGORIES)
    # STEP 2: CLEANING RESULTS
    logger.info("#2 Cleaning results...")
   
    canonical = clean_all(raw)
   
   
    # summary:
    total = 0
    for label, entities in canonical.items():
        logger.info(f"{label}: {len(entities)} entities")
        total += len(entities)
    logger.info(f"Total: {total} entities")
    
   
    # STEP 3: SAVING OUTPUT
    logger.info("#3 Saving output...")

    output_path = Path("data/dictionaries/hp_canonical.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(canonical, indent=2, ensure_ascii=False), encoding="utf-8")
    logger.info(f"Saved canonical entities to {output_path}")
        
   
   
   
if __name__ == "__main__":
    main()
   
   
   
