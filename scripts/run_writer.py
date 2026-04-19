"""
Write final dictionary .txt files for entity_dict.py.

Reads:  data/dictionaries/hp_canonical.json
        data/dictionaries/hp_aliases.json
Writes: data/dicts/<LABEL>.txt  (one file per label)

Format:
    Harry Potter
    >The Boy Who Lived
    >Harry
    Hermione Granger
    >Hermione
"""


import json
import logging
from pathlib import Path

from src.dict_builder.txt_writer import write_all_dicts

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("data/writer.log"),
    ]
)
logger = logging.getLogger(__name__)


def main():
    canonical_path = Path("data/dictionaries/hp_canonical.json")
    aliases_path = Path("data/dictionaries/hp_aliases.json")
    output_dir = Path("data/dictionaries/txts")
    if not canonical_path.exists():
        logger.error(f"Canonical dictionary not found at {canonical_path}. Please run the category crawler first.")
        return
    if not aliases_path.exists():
        logger.error(f"Alias dictionary not found at {aliases_path}. Please run the alias scraper first.")
        aliases = {}
    else:
        aliases = json.loads(aliases_path.read_text(encoding="utf-8"))
    
    canonical = json.loads(canonical_path.read_text(encoding="utf-8"))
    
    output_dir.mkdir(parents=True, exist_ok=True)
    
    write_all_dicts(canonical, aliases, output_dir)
    
    
if __name__ == "__main__":
    main()