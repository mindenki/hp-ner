import requests
import time
import json

BASE_URL = "https://harrypotter.fandom.com/api.php"

# ── Hand-picked categories ──────────────────────────────────────────────────

CATEGORIES = {
    
    "CHAR": [
        # Wizards
        "Wizards",
        "Dark wizards",
        "Death Eaters",
        "Death Eater defectors",
        "Unidentified Death Eaters",
        "Fictional Dark wizards",
        "Rookwood Gang",
        "Ashwinders (organisation)",
        "Poacher Pack",
        "Snatchers",
        "Unidentified Snatchers",
        "Unidentified Dark wizards",
        "Late-bloomers",
        # Ghosts
        "Ghosts",
        "Animal ghosts",
        "Ghost horses",
        "Unidentified ghosts",
        # Non-magic people
        "Non-magic people",
        "Unidentified non-magic people",
        # Squibs
        "Squibs",
],
    "LOC": [
        # Top level
        "Wizarding locations",
        # Shops
        "Apothecaries",
        "Broomstick shops",
        "Joke shops",
        "Wand shops",
        # Ministry locations
        "British Ministry of Magic locations",
        "British Ministry of Magic courtrooms",
        "British Ministry of Magic research wing",
        "French Ministry of Magic locations",
        "German Ministry of Magic locations",
        "Erkstag",
        # Diagon Alley
        "Diagon Alley",
        "Carkitt Market",
        "Horizont Alley",
        "Knockturn Alley",
        "Leaky Cauldron",
        # Gringotts
        "Gringotts vaults",
        # Magical schools
        "Magical schools",
        "Beauxbatons",
        "Beauxbatons locations",
        "Castelobruxo",
        "Durmstrang",
        "Durmstrang locations",
        "Hogwarts",
        "Hogwarts locations",
        "Hogwarts Express",
        "Ilvermorny",
        "Ilvermorny locations",
        "Mahoutokoro",
        "Mahoutokoro locations",
        "Uagadou",
        # Magically protected
        "Magically protected locations",
        "Magical Congress of the United States of America locations",
        "Malfoy Manor",
        "Unplottable locations",
        "Azkaban",
        # Other locations
        "Place Cachée",
        "Quidditch stadiums",
        "St Mungo's",
        "St Oswald's",
        "Wildlife reserves",
        "Magical Creatures Reserve",
        "Zonko's Joke Shop",
        # Wizarding towns
        "Wizarding towns",
        "Feldcroft",
        "Godric's Hollow",
        "Hogsmeade",
        "Shrieking Shack",
        "Three Broomsticks Inn",
        "Honeydukes",
        "Hogsmeade Post Office",
        "Ottery St Catchpole",
        "The Burrow",
    ],
    "ARTI": [
        # Top level
        "Magical objects",
        # Weapons/Sports
        "Amulets",
        "Bludgers",
        "Golden Snitches",
        # Broomsticks
        "Broomsticks",
        "Broomstick accessories",
        "Individual broomsticks",
        "Harry Potter's broomsticks",
        # Misc objects
        "Cauldrons",
        "Crystal balls",
        "Flying carpets",
        "Interdepartmental memos",
        "Portkeys",
        # Dark magic
        "Dark Magic artefacts",
        "Cursed objects",
        "Horcruxes",
        "Tom Riddle's Horcruxes",
        "Shrunken heads",
        # Goblin-made
        "Goblin-made objects",
        "Ancient magic repositories",
        "Objects made by Ragnuk",
        # Potions
        "Potions",
        "Counter-serums",
        "Fire-based potions",
        "Mental potions",
        "Awakening potions",
        "Love potions",
        "Sleep potions",
        "Potion ingredients",
        "Unidentified potions",
        # Prank devices
        "Prank devices",
        "Weasleys' Wizard Wheezes",
        "Skiving Snackbox",
        "WonderWitch",
        "Explosive Enterprises",
        "Muggle Magic",
        # Protective
        "Protective objects",
        "Dark Detectors",
        "Fireproof objects",
        # Sentient objects
        "Sentient objects",
        "Living books",
        "Portraits",
        "Paintings of creatures",
        "Unidentified portraits",
        "Suits of armour",
        "Armour pieces",
        "Gargoyles",
        "Wizard's Chess sets",
        # Wands
        "Wands",
        "Destroyed wands",
        "Wands by length",
        "Wands by material",
        "Wands by wandmaker",
        # Speaking objects
        "Howlers",
        # Triwizard
        "Triwizard Tournament objects",
    ],
    "ORG": [
    # Top level
        "Organisations",
        # Advocacy groups
        "Advocacy groups",
        "Dumbledore's first army",
        "Goblin rebels",
        "Ranrok's Loyalists",
        "New Salem Philanthropic Society",
        "Nocturnal Order of Tricks and Magical Exhibitions",
        "Society for the Promotion of Elfish Welfare",
        # Businesses
        "Businesses",
        "Banks",
        "Gringotts",
        "Broomstick manufacturers",
        "Car companies",
        "Clock companies",
        "Clothing companies",
        "Distilleries",
        "Gambling",
        "Grunnings",
        "Hotels",
        "Publishers",
        "Shaw News",
        "Record labels",
        "Shops",
        "Apothecaries",
        "Bookshops",
        "Broomstick shops",
        "Clothes shops",
        "Department stores",
        "Joke shops",
        "Kowalski Quality Baked Goods",
        "Music shops",
        "Perfume shops",
        "Pet shops",
        "Post offices",
        "Produce shops",
        "Quidditch shops",
        "Record shops",
        "Restaurants",
        "Sweet shops",
        "Travel agencies",
        "Wand shops",
        "Workshops",
        "Taxi companies",
        "Theatres",
        "Tyre companies",
        # Cliques
        "Cliques",
        "Dudley Dursley's gang",
        "Marauders",
        "Tom Riddle's gang",
        "Circle of Khanna",
        # Clubs
        "Clubs",
        "Duelling Clubs",
        "Fan clubs",
        "Hogwarts clubs",
        "Hogwarts Gobstone Club",
        "Slug Club",
        "Inquisitorial Squad",
        "Keepers (ancient magic)",
        # Defence organisations
        "Defence against the Dark Arts organisations",
        "Auror services",
        "Auror Office",
        # Gobstones
        "Gobstones organisations",
        "Gobstones teams",
        # Governments
        "Governments",
        "Magical governments",
        "International Confederation of Wizards",
        "Magical Congress of the United States of America",
        "Ministries of Magic",
        "Magical governments of the United Kingdom",
        "Muggle governments",
        "No-Maj governments of the United States of America",
        "Muggle government of the United Kingdom",
        # Law enforcement
        "Law enforcement agencies",
        "Department of Magical Law Enforcement",
        "Muggle-Born Registration Commission",
        "Wizengamot",
        # Military
        "Militias",
        "Terrorist groups",
        "Rookwood Gang",
        "Ashwinders (organisation)",
        "Poacher Pack",
        # Musical groups
        "Musical groups",
        "Frog Choir",
        "Place Cachée Jazz Band",
        "Weird Sisters",
        # Political
        "Political parties",
        "R",
        "Religious organisations",
        # Schools
        "Magical schools",
        "Beauxbatons",
        "Castelobruxo",
        "Durmstrang",
        "Hogwarts",
        "Ilvermorny",
        "Mahoutokoro",
        "Uagadou",
        "Muggle schools",
        "Smeltings",
        # Sports teams
        "Sports teams",
        "Football teams",
        "Quidditch teams",
        "British and Irish Quidditch League Quidditch teams",
        "Hogwarts Quidditch teams",
        "National Quidditch teams",
    ],
    "CREA": [
    # Top level
    "Creatures",
    # By danger classification
    "Flobberworms",
    "Horklumps",
    "Augureys",
    "Bowtruckles",
    "Chizpurfles",
    "Clabberts",
    "Diricawls",
    "Fairies",
    "Ghouls",
    "Gnomes",
    "Grindylows",
    "Imps",
    "Jobberknolls",
    "Mooncalves",
    "Porlocks",
    "Puffskeins",
    "Ramoras",
    "Winged horses",
    "Abraxans",
    "Thestrals",
    "Ashwinders",
    "Billywigs",
    "Bundimuns",
    "Crups",
    "Doxies",
    "Dugbogs",
    "Fire Crabs",
    "Fwoopers",
    "Glumbumbles",
    "Hippocampi",
    "Hippogriffs",
    "Hodags",
    "Knarls",
    "Kneazles",
    "Leprechauns",
    "Lobalugs",
    "Mackled Malaclaws",
    "Mokes",
    "Murtlaps",
    "Nifflers",
    "Nogtails",
    "Pixies",
    "Plimpies",
    "Red Caps",
    "Salamanders",
    "Frost Salamanders",
    "Sea serpents",
    "Shrakes",
    "Streelers",
    "Centaurs",
    "Demiguises",
    "Erumpents",
    "Golden Snidgets",
    "Graphorns",
    "Griffins",
    "Kelpies",
    "Merpeople",
    "Selkies",
    "Occamies",
    "Phoenixes",
    "Re'ems",
    "Runespoors",
    "Snallygasters",
    "Sphinxes",
    "Thunderbirds",
    "Trolls",
    "Unicorns",
    "Yetis",
    "Acromantulas",
    "Basilisks",
    "Chimaeras",
    "Dragons",
    "Individual dragons",
    "Horned Serpents",
    "Manticores",
    "Nundus",
    "Quintapeds",
    "Wampus cats",
    "Werewolves",
    # Demons
    "Demons",
    "Water demons",
    # Beings
    "Beasts",
    "Beings",
    "Giants",
    "Half-giants",
    "Goblins",
    "Corrupted goblins",
    "Hags",
    "House-elves",
    "Vampires",
    "Veela",
    "Part-Veela",
    # Spirits
    "Spirits",
    "Amortals",
    "Banshees",
    "Ghosts",
    # Shapeshifters
    "Shapeshifters",
    "Boggarts",
    "Maledictuses",
    "Metamorphmagi",
    "Obscurials",
    # Living dead / uncertain
    "Zombies",
    "Inferi",
    "Dwarfs",
    "Pukwudgies",
    # Misc magical
    "Chupacabras",
    "Classical Beasts",
    "Giant Squids",
    "Firedrakes",
    "Giant Dung Beetles",
    "Glow Bugs",
    "Jackalopes",
    "Leucrottas",
    "Matagots",
    "Qilins",
    "Swooping Evils",
    "Thornbacks",
    "Three-headed dogs",
    "Wyverns",
    "Zouwus",
    "Gargoyles",
    "Parasites",
    "Larvae",
],
    "SPELL": [
    # Top level
    "Spells",
    # Charms
    "Charms",
    "Dark charms",
    "Protective spells",
    # Curses/Hexes/Jinxes
    "Curses",
    "Unforgivable Curses",
    "Hexes",
    "Jinxes",
    "Special Jinxes",
    # Counter spells
    "Counter-spells",
    "Counter-charms",
    "Counter-curses",
    "Counter-jinxes",
    "Untransfigurations",
    # Spell types
    "Cleaning spells",
    "Healing spells",
    "Mental spells",
    "Opening spells",
    "Spell types",
    "Transfiguration spells",
    "Transforming spells",
    # Other
    "Spells of known incantation",
    "Spells of unknown incantation",
    "Spells with a light",
    "Unidentified spells",
    "Unintentional spells",
]
}


# -- Get categories -------------------------------------
def print_category_tree(category, depth=0, max_depth=4, visited=None):
    if visited is None:
        visited = set()
    
    if category in visited:
        return
    visited.add(category)

    indent = "  " * depth
    params = {
        "action": "query",
        "list": "categorymembers",
        "cmtitle": f"Category:{category}",
        "cmlimit": 500,
        "cmtype": "subcat",  # subcategories ONLY, no pages
        "format": "json"
    }

    while True:
        r = requests.get(BASE_URL, params=params).json()
        if "query" not in r:
            break
        for m in r["query"]["categorymembers"]:
            title = m["title"].replace("Category:", "")
            print(f"{indent}→ Subcategory: Category:{title}")
            if depth < max_depth:
                print_category_tree(title, depth + 1, max_depth, visited)
        if "continue" in r:
            params["cmcontinue"] = r["continue"]["cmcontinue"]
        else:
            break
        time.sleep(0.2)





# ── Crawler ─────────────────────────────────────────────────────────────────

def get_category_members(category):
    """Shallow crawl — pages only, no subcategories"""
    members = []
    params = {
        "action": "query",
        "list": "categorymembers",
        "cmtitle": f"Category:{category}",
        "cmlimit": 500,
        "cmtype": "page",  # no subcategories
        "format": "json"
    }
    while True:
        r = requests.get(BASE_URL, params=params).json()
        if "query" not in r:
            break
        members += [m["title"] for m in r["query"]["categorymembers"]]
        if "continue" in r:
            params["cmcontinue"] = r["continue"]["cmcontinue"]
        else:
            break
        time.sleep(0.2)
    return members




# ── Build ────────────────────────────────────────────────────────────────────

def build_dictionaries():
    dictionaries = {label: set() for label in CATEGORIES}

    # Category-based labels
    for label, cats in CATEGORIES.items():
        for cat in cats:
            print(f"[{label}] Crawling: {cat}")
            results = get_category_members(cat)
            dictionaries[label].update(results)
            print(f"  → {len(results)} entries")


    # Convert sets to sorted lists
    return {label: sorted(entries) for label, entries in dictionaries.items()}


# ── Run ──────────────────────────────────────────────────────────────────────

dictionaries = build_dictionaries()

print("\n── Summary ──")
for label, entries in dictionaries.items():
    print(f"{label}: {len(entries)} entries")

with open("hp_dictionaries.json", "w") as f:
    json.dump(dictionaries, f, indent=2, ensure_ascii=False)

print("\nSaved to hp_dictionaries.json")
