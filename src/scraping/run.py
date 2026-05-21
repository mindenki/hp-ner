"""Scraping orchestration: instantiate WikiScraper, start crawl, write JSONL.

One entry point called from ``scripts/prepare_annotation.py::_step_scrape``.
Default seed URL list lives here so the orchestrator stays thin.
"""
import logging
from pathlib import Path

from src.scraping.scraper import WikiScraper

logger = logging.getLogger(__name__)

HOME_URL = "https://harrypotter.fandom.com"
DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/79.0.3945.117 Safari/537.36"
    )
}
DEFAULT_DEPTH = 2
DEFAULT_DELAY_SECONDS = 2

SEED_URLS: list[str] = [
    # Characters
    "https://harrypotter.fandom.com/wiki/Harry_Potter",
    "https://harrypotter.fandom.com/wiki/Hermione_Granger",
    "https://harrypotter.fandom.com/wiki/Ron_Weasley",
    "https://harrypotter.fandom.com/wiki/Albus_Dumbledore",
    "https://harrypotter.fandom.com/wiki/Lord_Voldemort",
    "https://harrypotter.fandom.com/wiki/Severus_Snape",
    "https://harrypotter.fandom.com/wiki/Draco_Malfoy",
    "https://harrypotter.fandom.com/wiki/Rubeus_Hagrid",
    "https://harrypotter.fandom.com/wiki/Sirius_Black",
    "https://harrypotter.fandom.com/wiki/Minerva_McGonagall",
    "https://harrypotter.fandom.com/wiki/Neville_Longbottom",
    "https://harrypotter.fandom.com/wiki/Luna_Lovegood",
    "https://harrypotter.fandom.com/wiki/Ginny_Weasley",
    "https://harrypotter.fandom.com/wiki/Remus_Lupin",
    "https://harrypotter.fandom.com/wiki/Bellatrix_Lestrange",
    # Locations
    "https://harrypotter.fandom.com/wiki/Hogwarts_Castle",
    "https://harrypotter.fandom.com/wiki/Diagon_Alley",
    "https://harrypotter.fandom.com/wiki/Hogsmeade",
    "https://harrypotter.fandom.com/wiki/Azkaban",
    "https://harrypotter.fandom.com/wiki/Ministry_of_Magic",
    "https://harrypotter.fandom.com/wiki/Forbidden_Forest",
    "https://harrypotter.fandom.com/wiki/Gringotts_Wizarding_Bank",
    "https://harrypotter.fandom.com/wiki/Knockturn_Alley",
    "https://harrypotter.fandom.com/wiki/Grimmauld_Place",
    # Organizations
    "https://harrypotter.fandom.com/wiki/Order_of_the_Phoenix",
    "https://harrypotter.fandom.com/wiki/Death_Eaters",
    "https://harrypotter.fandom.com/wiki/Gryffindor",
    "https://harrypotter.fandom.com/wiki/Slytherin",
    "https://harrypotter.fandom.com/wiki/Hufflepuff",
    "https://harrypotter.fandom.com/wiki/Ravenclaw",
    "https://harrypotter.fandom.com/wiki/Auror",
    "https://harrypotter.fandom.com/wiki/Hogwarts_staff",
    # Spells
    "https://harrypotter.fandom.com/wiki/List_of_spells",
    "https://harrypotter.fandom.com/wiki/Expelliarmus",
    "https://harrypotter.fandom.com/wiki/Avada_Kedavra",
    "https://harrypotter.fandom.com/wiki/Expecto_Patronum",
    "https://harrypotter.fandom.com/wiki/Alohomora",
    "https://harrypotter.fandom.com/wiki/Accio",
    # Creatures
    "https://harrypotter.fandom.com/wiki/List_of_creatures",
    "https://harrypotter.fandom.com/wiki/Dragon",
    "https://harrypotter.fandom.com/wiki/House-elf",
    "https://harrypotter.fandom.com/wiki/Basilisk",
    "https://harrypotter.fandom.com/wiki/Hippogriff",
    "https://harrypotter.fandom.com/wiki/Dementor",
    "https://harrypotter.fandom.com/wiki/Phoenix",
    "https://harrypotter.fandom.com/wiki/Werewolf",
    "https://harrypotter.fandom.com/wiki/Centaur",
    "https://harrypotter.fandom.com/wiki/Giant",
    # Artifacts
    "https://harrypotter.fandom.com/wiki/Horcrux",
    "https://harrypotter.fandom.com/wiki/Deathly_Hallows",
    "https://harrypotter.fandom.com/wiki/Elder_Wand",
    "https://harrypotter.fandom.com/wiki/Invisibility_cloak",
    "https://harrypotter.fandom.com/wiki/Philosopher%27s_Stone",
    "https://harrypotter.fandom.com/wiki/Marauder%27s_Map",
    "https://harrypotter.fandom.com/wiki/Sorting_Hat",
    "https://harrypotter.fandom.com/wiki/Time-Turner",
    "https://harrypotter.fandom.com/wiki/Triwizard_Cup",
    "https://harrypotter.fandom.com/wiki/Pensieve",
]


def scrape_entrypoint(output_path: Path) -> None:
    """Crawl the HP Fandom wiki starting from SEED_URLS, write JSONL to ``output_path``."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    scraper = WikiScraper(
        SEED_URLS, HOME_URL, DEFAULT_DEPTH, DEFAULT_HEADERS, DEFAULT_DELAY_SECONDS, str(output_path),
    )
    scraper.start_scraping()
    logger.info("scrape_entrypoint: wrote %s", output_path)
