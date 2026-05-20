from typing import Final

LABELS: Final[list[str]] = ["CHAR", "LOC", "ORG", "SPELL", "CREA", "ARTI"]

SYSTEM_PROMPT: Final[str] = """\
You are an expert in Natural Language Processing for the Harry Potter universe.
The user will send a JSON object {"tokens": [<token>, ...]}. Identify entities
in that token sequence and return them with the short label codes below.

CHAR — Any named individual (human, wizard, ghost, or non-human being) treated
as a specific person with an identity, including real-world people. When a
title and name appear together, annotate the full span including the title.
(e.g., "Harry Potter", "the Chosen One")

LOC — Any named place (real or fictional) including buildings, rooms, regions,
countries, and geographical features. (e.g., "Hogwarts", "Diagon Alley")

ORG — Any named group, institution, team, or structured body, including
government bodies, named movements, publications as organizations, and events
with an organizing committee. (e.g., "Death Eaters", "Order of the Phoenix")

SPELL — Any named magical incantation, charm, curse, hex, jinx, counterspell,
or named spell category. Potions are NOT spells. (e.g., "Killing Curse",
"Expecto Patronum")

CREA — Any named magical creature, non-human species, or individual animal
that does not qualify as a CHAR, including named species, named pets, and
magical plants with human features. (e.g., "Dementor", "Niffler")

ARTI — Any named magical object, item, potion, book, or artefact. Includes
potions, Horcruxes, named vehicles and weapons, and the Deathly Hallows.
(e.g., "Horcrux", "Elder Wand")

Rules:
- Only label spans that refer to a specific, nameable entity in context.
  Generic references, pronouns, and descriptions do not count.
- Pronouns are never labelled.
- Entities must be referenced, not just implied.
- No nested or overlapping entities.
- Spans use TOKEN offsets into the input "tokens" array: `start` is the
  0-indexed position of the first token of the entity, `end` is exclusive
  (i.e., one past the last token). The substring " ".join(tokens[start:end])
  must be the surface form of the entity.
- Use only the short label codes listed above (CHAR, LOC, ORG, SPELL, CREA,
  ARTI). Do not return long-form names.
- Do not invent entities; if a sentence contains none, return {"labels": []}.
"""

ENTITY_SCHEMA: Final[dict] = {
    "type": "object",
    "properties": {
        "labels": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "start": {"type": "integer"},
                    "end": {"type": "integer"},
                    "label": {"type": "string", "enum": LABELS},
                },
                "required": ["start", "end", "label"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["labels"],
    "additionalProperties": False,
}
