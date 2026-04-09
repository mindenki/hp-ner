"""
Dict file writer.

Reads canonical + alias names and writes one .txt file for each 6 labels, with one name per line, in the format
expected by enity_dict.py:
        Harry Potter
        >The Boy Who Lived
        >The Chosen One
        >Harry
        Hermione Granger
        >Hermione
"""


import logging


from pathlib import Path

logger = logging.getLogger(__name__)

def _sort_longest_first(names: list[str]) -> list[str]:
    """ Sort by descending length to ensure that multi-word names match greedily."""
    
    return sorted(names, key=lambda s: len(s), reverse=True)


def _write_dict_file(canonical_names: list[str], aliases: dict[str, list[str]], path: Path) -> None:
    """ Writes a single .txt file for one label. """
    
    path.parent.mkdir(parents=True, exist_ok=True)
    
    ordered = _sort_longest_first(canonical_names)
    
    lines = []
    for name in ordered:
        lines.append(name)
        for alias in sorted(aliases.get(name, [])):
            lines.append(f">{alias}")
    
    path.write_text("\n".join(lines), encoding="utf-8")
    logger.info((f"  wrote {path}  ({len(ordered)} entries)"))
    
    
LABEL_TO_FILENAME = {
    "CHAR": "character.txt",
    "LOC": "location.txt",
    "ORG": "organization.txt",
    "CREA": "creature.txt",
    "ARTI": "artifact.txt",
    "SPELL": "spell.txt",
}
    
    
    
def write_all_dicts(canonical: dict[str, list[str]], aliases: dict[str, dict[str, list[str]]], output_dir: Path=None) -> None:
    """ Write one .txt file for each label, combining canonical and alias names. """
    if output_dir is None:
        output_dir = Path("data/dictionaries/txts")
        
    for label, names in canonical.items():
        filename = LABEL_TO_FILENAME.get(label, f"{label.lower()}.txt")
        path = output_dir / filename
        logger.info(f"Writing dict file for label '{label}' to {path}...")
        _write_dict_file(names, aliases.get(label, {}), path)

        
    