"""Generate minimal dummy JSONL batches for testing the Doccano setup scripts.

Writes a handful of Harry Potter sentences (with gold labels) into
data/to_annotate/ so you can test setup_doccano_project.py and the full
import/export/merge pipeline without running the silver labeling pipeline first.

Usage:
    uv run python scripts/make_dummy_data.py
"""

import json
from pathlib import Path

# fmt: off
OVERLAP = [
    {"text": "Harry cast Expelliarmus and Draco 's wand flew across the room .", "label": [[0, 5, "Character"], [18, 30, "Spell"], [35, 40, "Character"]]},
    {"text": "Dumbledore looked at Harry over his half-moon spectacles .", "label": [[0, 9, "Character"], [21, 26, "Character"]]},
    {"text": "Hermione ran to the library in Hogwarts to research the spell .", "label": [[0, 8, "Character"], [30, 38, "Location"]]},
    {"text": "The Order of the Phoenix met secretly at Grimmauld Place .", "label": [[4, 26, "Organization"], [41, 55, "Location"]]},
    {"text": "Ron borrowed the Invisibility Cloak from Harry before the match .", "label": [[0, 3, "Character"], [17, 32, "Artifact"], [38, 43, "Character"]]},
]

PETER = [
    {"text": "Voldemort raised his wand and spoke Avada Kedavra into the darkness .", "label": [[0, 9, "Character"], [35, 48, "Spell"]]},
    {"text": "Buckbeak soared above the Forbidden Forest with Hagrid watching below .", "label": [[0, 8, "Creature"], [25, 41, "Location"], [47, 53, "Character"]]},
    {"text": "The Elder Wand cracked as Dumbledore snapped it in two .", "label": [[4, 13, "Artifact"], [25, 34, "Character"]]},
]

HANNA = [
    {"text": "Dobby warned Harry not to return to Hogwarts for his own safety .", "label": [[0, 5, "Creature"], [13, 18, "Character"], [36, 44, "Location"]]},
    {"text": "The Ministry of Magic sent an owl to the Dursleys at Privet Drive .", "label": [[4, 22, "Organization"], [52, 64, "Location"]]},
    {"text": "Lumos lit the dark corridor as Neville crept past the portrait .", "label": [[0, 5, "Spell"], [30, 37, "Character"]]},
]

ZITA = [
    {"text": "The Marauder 's Map showed every person inside Hogwarts castle .", "label": [[4, 19, "Artifact"], [47, 55, "Location"]]},
    {"text": "Aragog 's children descended from the Forbidden Forest at midnight .", "label": [[0, 6, "Creature"], [37, 53, "Location"]]},
    {"text": "Sirius Black escaped from Azkaban and hid in the cave near Hogsmeade .", "label": [[0, 12, "Character"], [25, 32, "Location"], [59, 68, "Location"]]},
]

ANIS = [
    {"text": "Snape brewed Veritaserum in the dungeons beneath Hogwarts .", "label": [[0, 5, "Character"], [13, 23, "Spell"], [49, 57, "Location"]]},
    {"text": "The Sorting Hat placed Hermione in Gryffindor without hesitation .", "label": [[4, 15, "Artifact"], [22, 30, "Character"], [34, 44, "Organization"]]},
    {"text": "Fawkes the phoenix burst into flames on Dumbledore 's desk .", "label": [[0, 6, "Creature"], [39, 48, "Character"]]},
]
# fmt: on

BATCHES = {
    "overlap_set.jsonl": OVERLAP,
    "peter_unique.jsonl": PETER,
    "hanna_unique.jsonl": HANNA,
    "zita_unique.jsonl": ZITA,
    "anis_unique.jsonl": ANIS,
}


def main() -> None:
    out = Path("data/to_annotate")
    out.mkdir(parents=True, exist_ok=True)

    for filename, records in BATCHES.items():
        path = out / filename
        with path.open("w", encoding="utf-8") as f:
            for record in records:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
        print(f"Wrote {len(records):>2} sentences → {path}")

    print(
        "\nTest the full setup with:\n"
        "  uv run python scripts/setup_doccano_project.py\n"
        "Then open http://localhost:8000 to verify the project and labels."
    )


if __name__ == "__main__":
    main()
