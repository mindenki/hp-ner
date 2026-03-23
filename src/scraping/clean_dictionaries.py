import json
import re

with open("hp_dictionaries.json", "r") as f:
    dicts = json.load(f)

# ── Shared patterns to remove from ALL categories ──────────────────────────

GLOBAL_SKIP_SUBSTRINGS = [
    # Book/film/game titles
    "Harry Potter and the",
    "Fantastic Beasts",
    "LEGO",
    "Wonderbook",
    "Harry Potter:",
    "Hogwarts Legacy",
    "Harry Potter (website)",
    "Harry Potter Trading Card Game",
    "Pottermore",
    # Wiki metadata
    "Template:",
    "User:",
    "Category:",
    # Real-world brands / orgs
    "Adidas", "Nike", "Coca-Cola", "Blockbuster", "Samsung", "Honda",
    "Visa", "MasterCard", "Ferrari", "Rolls Royce", "Vauxhall",
    "National Health Service", "European Union", "BuzzFeed",
    "Nintendo", "Fujifilm",
]

GLOBAL_SKIP_EXACT = {
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

def is_date_or_year(s):
    """Filters out standalone years, dates, centuries"""
    return bool(re.match(r"^\d{1,4}s?$", s.strip())) or \
           bool(re.match(r"^\d+ \w+$", s.strip())) or \
           "century" in s.lower() or \
           bool(re.match(r"^\d{4}[-–]\d{4}.*", s.strip()))

def global_clean(entries):
    cleaned = []
    for e in entries:
        if e in GLOBAL_SKIP_EXACT:
            continue
        if is_date_or_year(e):
            continue
        if any(p in e for p in GLOBAL_SKIP_SUBSTRINGS):
            continue
        cleaned.append(e)
    return cleaned

# ── Per-category extra filters ─────────────────────────────────────────────

def clean_char(entries):
    skip = [
        "Unidentified",           # too vague for NER
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
    result = []
    for e in entries:
        if e in skip_exact:
            continue
        if any(s in e for s in skip):
            continue
        result.append(e)
    return result

def clean_loc(entries):
    skip_substrings = [
        # Food and drinks
        "Butterbeer", "Pumpkin juice", "Firewhisky", "Mead",
        "Chocolate", "Candy", "Sweet", "Fudge", "Toffee",
        "Soup", "Cake", "Pie", "Pudding", "Biscuit",
        # Events / battles / duels
        "Battle of", "Duel at", "Duel in", "Attack at", "Attack in",
        "Skirmish at", "Skirmish in", "Siege of", "Raid on",
        "Massacre at", "Infiltration of",
        # Documents / forms / letters
        "letter", "form", "certificate", "badge", "permit",
        "notice", "report", "booklet", "exam", "homework",
        # Non-location wiki pages
        "Template:", "Brilliant Event:", "Registry",
        # Food
        "Apple Rings", "Assorted", "Caramel", "Sour", "Strips",
        "Chocolate", "Green Apple",
    ]
    skip_exact = {
        "Hogwarts Legacy", "Pottermore", "Calamity",
    }
    result = []
    for e in entries:
        if e in skip_exact:
            continue
        if any(s.lower() in e.lower() for s in skip_substrings):
            continue
        result.append(e)
    return result

def clean_arti(entries):
    skip_substrings = [
        # Characters that leaked in
        "Albus Dumbledore", "Alastor Moody", "Bellatrix Lestrange",
        "Gilderoy Lockhart", "Horace Slughorn", "Minerva McGonagall",
        "Severus Snape", "Voldemort", "Dolores Umbridge",
        # Classes / subjects
        "Potions (class)", "Charms (class)", "Transfiguration (class)",
        "Defence Against", "Herbology", "Astronomy",
        # Events
        "Battle of", "Duel at", "Skirmish",
        # Wiki/game meta
        "Template:", "Registry", "Brilliant Event", "Pottermore",
        "Harry Potter:", "Harry Potter and the", "Hogwarts Legacy",
        # Potions Association / Club (orgs, not artifacts)
        "Potions Association", "Potions Club",
    ]
    result = []
    for e in entries:
        if any(s in e for s in skip_substrings):
            continue
        result.append(e)
    return result

def clean_crea(entries):
    skip_substrings = [
        "Harry Potter and the",
        "Harry Potter:",
        "Hogwarts Legacy",
        "Fantastic Beasts",
        "Wonderbook",
        "LEGO",
        "Pottermore",
        "Trading Card Game",
        "video game",
        "film",
        "(real)",
        "real-world",
        "companion book",
        "Original Screenplay",
        "website",
        "for Kinect",
        "Magic Awakened",
        "Puzzles",
        "Wizards Unite",
        "Hogwarts Mystery",
        "Template:",
        "Registry",
        "Creator:",
    ]
    result = []
    for e in entries:
        if any(s in e for s in skip_substrings):
            continue
        result.append(e)
    return result

def clean_spell(entries):
    """Spell list is the most broken — keep only plausible spell names"""
    # A real spell name is typically short, often ends in -us/-o/-io/-em/-mus
    # or is a known spell phrase. We'll use a whitelist approach:
    # keep entries that don't contain obvious non-spell patterns.
    skip_substrings = [
        "Harry Potter", "Fantastic Beasts", "LEGO", "Hogwarts Legacy",
        "Wonderbook", "Pottermore", "Trading Card Game",
        "video game", "(film)", "Original Screenplay", "(real)",
        "(real-world)", "companion book", "website", "for Kinect",
        "Magic Awakened", "Puzzles & Spells", "Wizards Unite",
        "Hogwarts Mystery", "Template:", "Creator:",
        # Characters
        "Albus Dumbledore", "Harry Potter (", "Hermione Granger",
        "Voldemort", "Severus Snape", "Bellatrix", "Draco Malfoy",
        "Ron Weasley", "Neville", "Luna Lovegood",
        # Locations
        "Hogwarts Castle", "Azkaban", "Diagon Alley", "Ministry of Magic",
        "Hogsmeade", "Forbidden Forest", "Gringotts",
        "Grimmauld Place", "Shell Cottage", "Malfoy Manor",
        # Objects / potions
        "Polyjuice Potion", "Felix Felicis", "Philosopher's Stone",
        "Time-Turner", "Invisibility Cloak", "Horcrux",
        "Marauder's Map", "Goblet of Fire", "Elder Wand",
        # Organizations
        "Order of the Phoenix", "Death Eaters", "Dumbledore's Army",
        "Inquisitorial Squad", "Auror Office", "Ministry of Magic",
        "Quidditch", "Holyhead Harpies", "Puddlemere",
        # Misc non-spells
        "school year", "year", "J. K. Rowling", "Comet 140",
    ]
    skip_exact = {
        "Charm", "Hex", "Jinx", "Curse", "Spell", "Magic",
        "Incantation", "Modifier", "Dark Arts", "Counter-spell",
        "Counter-charm", "Counter-curse", "Transfiguration",
        "Conjuration", "Vanishment", "Switching",
    }
    result = []
    for e in entries:
        if e in skip_exact:
            continue
        if is_date_or_year(e):
            continue
        if any(s in e for s in skip_substrings):
            continue
        result.append(e)
    return result

def clean_org(entries):
    skip_substrings = [
        # Real-world brands/companies
        "Adidas", "Nike", "Ferrari", "Honda", "Rolls Royce", "Vauxhall",
        "Chevrolet", "Ford", "Samsung", "Fujifilm", "TDK", "Whirlpool",
        "Visa", "MasterCard", "Barclays", "BuzzFeed", "Blockbuster",
        "Nintendo", "Coldplay", "Gorillaz",
        # Real-world institutions
        "National Health Service", "European Union", "National Lottery",
        "Metropolitan Police", "Royal Air Force", "Royal Mail",
        "Cambridge University", "Eton", "Labour Party", "Republican Party",
        # Food items
        "Paczki", "Pierogi", "Piernik", "Golabki", "Challah",
        "Faworki", "Babka", "Sernik", "Makowiec",
        # Wiki/game meta
        "Template:", "Brilliant Event:", "Pottermore",
        "Harry Potter and the", "Harry Potter:", "Hogwarts Legacy",
        "LEGO", "Fantastic Beasts", "Wonderbook",
        # Events
        "Battle of", "Duel at", "Skirmish", "Trial of",
        # Documents
        "letter", "form", "certificate", "badge", "permit",
        "notice", "booklet", "exam", "homework", "receipt",
        # characters
        "Admonitor", "Balloon Carriage", "Abigail Grey", "Aurelius Dumbledore"
    ]
    result = []
    for e in entries:
        if any(s in e for s in skip_substrings):
            continue
        result.append(e)
    return result

# ── Run all cleaning ───────────────────────────────────────────────────────

cleaners = {
    "CHAR":  clean_char,
    "LOC":   clean_loc,
    "ARTI":  clean_arti,
    "CREA":  clean_crea,
    "SPELL": clean_spell,
    "ORG":   clean_org,
}

cleaned_dicts = {}
for label, entries in dicts.items():
    step1 = global_clean(entries)
    step2 = cleaners[label](step1)
    # Final dedup and sort
    cleaned_dicts[label] = sorted(set(step2))
    print(f"{label}: {len(entries):>5} → {len(cleaned_dicts[label]):>5} entries")

with open(".../data/dictionaries/hp_dictionaries_clean.json", "w") as f:
    json.dump(cleaned_dicts, f, indent=2, ensure_ascii=False)

print("\nSaved to hp_dictionaries_clean.json")