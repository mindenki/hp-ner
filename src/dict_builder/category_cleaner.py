"""
Cleaning filters for the raw HP category crawler results.

Manually curated rules to remove noise from the raw category members, which can include:
- Non-entity pages (e.g. "Template:Infobox character", "Category:Wizards")
- Irrelevant entities that bleed into other domains (e.g. "Adidas", "European Union")
- Subcategories that bleed into other domains (e.g. "People in Locations", "Wizards by house")
"""

import re
import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Global noise

_GLOBAL_SKIP_SUBSTRINGS = [
    "Harry Potter and the",
    "Fantastic Beasts",
    "LEGO",
    "Wonderbook",
    "Harry Potter:",
    "Hogwarts Legacy",
    "Harry Potter (website)",
    "Harry Potter Trading Card Game",
    "Pottermore",
    "Template:",
    "User:",
    "Category:",
    "Adidas", "Nike", "Coca-Cola", "Blockbuster", "Samsung", "Honda",
    "Visa", "MasterCard", "Ferrari", "Rolls Royce", "Vauxhall",
    "National Health Service", "European Union", "BuzzFeed",
    "Nintendo", "Fujifilm",
    "'s parents", "'s mother", "'s father", "'s siblings",
    "'s children", "'s friends", "'s gang", "'s followers",
    "'s aunt", "'s uncle", "'s cousin", "'s grandm", "'s grandp",
    "'s landlord", "'s neighbour", "'s neighbor", "'s boss",
    "'s wife", "'s husband", "'s daughter", "'s son",
    "'s associate", "'s successor", "'s predecessor",
    "'s mentor", "'s partner", "'s secretary", "'s assistant",
    # List and meta entries
    "List of ",
    "Essay on ",
    "Notes on ",
    "Study of ",
    # Brilliant Event (wiki game content)
    "Brilliant Event",
    # (class) suffix — spills from course categories into artifacts/spells
    "(class)",
    # Squib/Snatchers/Death Eater role tags that slipped through
    "Template:",   # already present, keep
    "User:",        # already present, keep
]

_GLOBAL_SKIP_EXACT = {
    "Magic",
    "Wizardkind",
    "Wizarding world",
    "Non-magic people",
    "Human",
    "Squib",
    "Animagus",
    "Parseltongue",
    "Legilimency",
    "Occlumency",
    "Secondary",
    "Late-bloomer",
    "Underbeing",
    "Half-breed",
}

def _is_date_or_year(s: str) -> bool:
    s = s.strip()
    return (
        bool(re.match(r"^\d{1,4}s?$", s))
        or bool(re.match(r"^\d+ \w+$", s))
        or "century" in s.lower()
        or bool(re.match(r"^\d{4}[-–]\d{4}.*", s))
    )
    
def _starts_with_digit(s: str) -> bool:
    """Catches entries like '1980s Hogwarts Gobstones Tournament champion'."""
    return bool(s) and s[0].isdigit()
    
def _global_clean(entries: list[str]) -> list[str]:
    result = []
    for e in entries:
        if e in _GLOBAL_SKIP_EXACT:
            continue
        if _is_date_or_year(e):
            continue
        if _starts_with_digit(e):         
            continue
        if any(p in e for p in _GLOBAL_SKIP_SUBSTRINGS):
            continue
        result.append(e)
    return result

# Per-label noise

# CHARACTER
def _clean_char(entries: list[str]) -> list[str]:
    skip_substrings = [
        "Unidentified",
        "'s parents", "'s mother", "'s father", "'s siblings",
        "'s children", "'s friends", "'s gang", "'s followers",
        "spectators", "participants", "members", "victims",
        "Template", "portrait", "Portrait",
    ]
    skip_exact = {
        "Death Eaters", "Snatchers", "Rookwood Gang",
        "Ashwinders", "Most Dangerous Dark Wizards of All Time",
        "Fallen Fifty", "Protest floats", "Witch and Wizard Couple",
    }
    
    
    return [
        e for e in entries
        if e not in skip_exact
        and not any(s in e for s in skip_substrings)
    ]
    

# LOCATION
def _clean_loc(entries: list[str]) -> list[str]:
    skip_substrings = [
        "Butterbeer", "Pumpkin juice", "Firewhisky", "Mead",
        "Chocolate", "Candy", "Sweet", "Fudge", "Toffee",
        "Soup", "Cake", "Pie", "Pudding", "Biscuit",
        "Battle of", "Duel at", "Duel in", "Attack at", "Attack in",
        "Skirmish at", "Skirmish in", "Siege of", "Raid on",
        "Massacre at", "Infiltration of",
        "letter", "form", "certificate", "badge", "permit",
        "notice", "report", "booklet", "exam", "homework",
        "Template:", "Brilliant Event:", "Registry",
        "Apple Rings", "Assorted", "Caramel", "Sour", "Strips", "Green Apple",
            "Rings",          # Apple Rings, Peach Rings, etc.
    "Strips",         # Sour Strips, Strawberry Strips
    "Fudge",
    "Toffee",
    "Biscuit",
    "Caramel",
    "Gummy",
    "Gummi",
    "Pasty",
    "Rock",           # Fruit Rock (but watch for 'Azkaban's Rock', use carefully)
    "Drooble",
    "Crystallised",
    "Bonbon",
    "Humbug",
    "Sherbet",
    # Events — extend the existing list
    "Battle for",
    "Battle of",
    "Raid on",
    "Siege of",
    "Skirmish in",
    "Skirmish at",
    "Attack in",
    "Attack on",
    "Attack at",
    "Escape from",
    "Infiltration of",
    "Murder of",
    "Massacre at",
    # Documents / media
    "notebook",
    "Permission form",
    "permission form",
    "letter",
    "leaflet",
    "certificate",
    "Programme",       # Hogwarts Yule Ball Programme etc.
    "Booklet",
    # Game event strings
    "Brilliant Event",
    "Registry",
    # Artifacts that bled into LOC via broad categories
    "Daedalian Keys",
    "Box of confiscated",
    "Hogwarts Pensieve",
    "Hogwarts Tapestry",
    ]
    skip_exact: set[str] = {"Hogwarts Legacy", "Pottermore", "Calamity"}
    return [
        e for e in entries
        if e not in skip_exact
        and not any(s.lower() in e.lower() for s in skip_substrings)
    ]
    
    
# ARTIFACT
def _clean_arti(entries: list[str]) -> list[str]:
    skip_substrings = [
        "Albus Dumbledore", "Alastor Moody", "Bellatrix Lestrange",
        "Gilderoy Lockhart", "Horace Slughorn", "Minerva McGonagall",
        "Severus Snape", "Voldemort", "Dolores Umbridge",
        "Potions (class)", "Charms (class)", "Transfiguration (class)",
        "Defence Against", "Herbology", "Astronomy",
        "Battle of", "Duel at", "Skirmish",
        "Template:", "Registry", "Brilliant Event", "Pottermore",
        "Potions Association", "Potions Club",
    ]
    return [e for e in entries if not any(s in e for s in skip_substrings)]

# CREATURE
def _clean_crea(entries: list[str]) -> list[str]:
    skip_substrings = [
        "(real)", "real-world", "companion book", "Original Screenplay",
        "website", "for Kinect", "Magic Awakened", "Puzzles",
        "Wizards Unite", "Hogwarts Mystery", "Template:", "Registry",
        "Creator:", "video game", "film",
        "Abigail Grey",
    "Cassandra Vole",
    "Diego Caplan",
    "Eddie Cleaver",
    "Edgar Cloggs",
    "Edmund Grubb",
    # Spells that ended up in CREA
    "Fairy Cakes to Fairies",     # this is a Transfiguration spell
    "Draconifors Spell",           # spell, not creature
    "Thimble to Thestral",         # spell
    "Human to thunderbird spell",  # spell
    # Catch-all: anything with " Spell" or " Charm" is probably a spell
    " Spell",
    " Charm",
    ]
    return [e for e in entries if not any(s in e for s in skip_substrings)]


# SPELL
def _clean_spell(entries: list[str]) -> list[str]:
    skip_substrings = [
        "Harry Potter", "Fantastic Beasts", "LEGO", "Hogwarts Legacy",
        "Wonderbook", "Pottermore", "Trading Card Game",
        "video game", "(film)", "Original Screenplay", "(real)",
        "(real-world)", "companion book", "website", "for Kinect",
        "Magic Awakened", "Puzzles & Spells", "Wizards Unite",
        "Hogwarts Mystery", "Template:", "Creator:",
        "Albus Dumbledore", "Harry Potter (", "Hermione Granger",
        "Voldemort", "Severus Snape", "Bellatrix", "Draco Malfoy",
        "Ron Weasley", "Neville", "Luna Lovegood",
        "Hogwarts Castle", "Azkaban", "Diagon Alley", "Ministry of Magic",
        "Hogsmeade", "Forbidden Forest", "Gringotts",
        "Grimmauld Place", "Shell Cottage", "Malfoy Manor",
        "Polyjuice Potion", "Felix Felicis", "Philosopher's Stone",
        "Time-Turner", "Invisibility Cloak", "Horcrux",
        "Marauder's Map", "Goblet of Fire", "Elder Wand",
        "Order of the Phoenix", "Death Eaters", "Dumbledore's Army",
        "Inquisitorial Squad", "Auror Office", "Ministry of Magic",
        "Quidditch", "Holyhead Harpies", "Puddlemere",
        "school year", "year", "J. K. Rowling", "Comet 140",
        "Essay on ",
    "List of spells",
    "Unforgivable Curses Appeals",
    "Unforgivable Curses and Their Legal",
    "The Imperius Curse and How",
    "Intercepting a Counter Incantation",
    "Scuba-Spells",              # book title
    "Spell-ing Wasp",           # competition name
    "Slytherin's Scriptorium",
    ]
    skip_exact: set[str] = {
        "Charm", "Hex", "Jinx", "Curse", "Spell", "Magic",
        "Incantation", "Modifier", "Dark Arts", "Counter-spell",
        "Counter-charm", "Counter-curse", "Transfiguration",
        "Conjuration", "Vanishment", "Switching",
    }
    return [
        e for e in entries
        if e not in skip_exact
        and not _is_date_or_year(e)
        and not any(s in e for s in skip_substrings)
    ]
    
# ORGANIZATION
def _clean_org(entries: list[str]) -> list[str]:
    skip_substrings = [
        "Adidas", "Nike", "Ferrari", "Honda", "Rolls Royce", "Vauxhall",
        "Chevrolet", "Ford", "Samsung", "Fujifilm", "TDK", "Whirlpool",
        "Visa", "MasterCard", "Barclays", "BuzzFeed", "Blockbuster",
        "Nintendo", "Coldplay", "Gorillaz",
        "National Health Service", "European Union", "National Lottery",
        "Metropolitan Police", "Royal Air Force", "Royal Mail",
        "Cambridge University", "Eton", "Labour Party", "Republican Party",
        "Paczki", "Pierogi", "Piernik", "Golabki", "Challah",
        "Faworki", "Babka", "Sernik", "Makowiec",
        "Template:", "Brilliant Event:", "Pottermore",
        "Battle of", "Duel at", "Skirmish", "Trial of",
        "letter", "form", "certificate", "badge", "permit",
        "notice", "booklet", "exam", "homework", "receipt",
        "Admonitor", "Balloon Carriage", "Abigail Grey", "Aurelius Dumbledore",
        "Babka",
    "Challah",
    "Faworki",
    "Golabki",
    "Makowiec",
    "Paczki",
    "Piernik",
    "Pierogi",
    "Sernik",
    "Obwarzanek",
    "Kielbasa",
    "Pasztecik",
    # Individual characters that leaked into ORG
    # (from "Clubs" or "Cliques" categories where a character is also listed)
    # Best caught by cross-referencing CHAR list
    # Game / wiki meta
    "Brilliant Event",
    "Registry",
    # Template entries already caught globally, but ORG had specific ones:
    "Template:Organisation infobox",
    "Template:Publisher infobox",
    "Template:Quidditch Team infobox",
    ]
    return [e for e in entries if not any(s in e for s in skip_substrings)]




# CLEANING MAP
_LABEL_TO_CLEANER = {
    "CHAR": _clean_char,
    "LOC": _clean_loc,
    "ARTI": _clean_arti,
    "CREA": _clean_crea,
    "SPELL": _clean_spell,
    "ORG": _clean_org,
}


# cleaning function

def clean_all(raw: dict[str,list[str]]) -> dict[str, list[str]]:
    """ Apply global and per-label cleaning rules to the raw categories. 
    
        Args:
            raw: Label -> list of uncleaned entries (output of category crawler).
            
        Returns:
            Label -> list of cleaned entries (after applying global and per-label rules).
    """
    
    cleaned = {}
    
    for label, entries in raw.items():
        logger.info(f"Cleaning {len(entries)} raw entries for label '{label}'...")
        
        # global cleaning
        global_cleaned = _global_clean(entries)
        logger.info(f"  {len(global_cleaned)} entries remain after global cleaning.")
        
        # per-label cleaning
        cleaner = _LABEL_TO_CLEANER.get(label)
        if cleaner:
            label_cleaned = cleaner(global_cleaned)
            logger.info(f"  {len(label_cleaned)} entries remain after '{label}'-specific cleaning.")
            cleaned[label] = label_cleaned
        else:
            logger.warning(f"No specific cleaner found for label '{label}', skipping per-label cleaning.")
            cleaned[label] = global_cleaned
            
    return cleaned