from typing import Final

LABELS: Final[list[str]] = ["CHAR", "LOC", "ORG", "SPELL", "CREA", "ARTI"]
IOB_TAGS: Final[list[str]] = ["O"] + [f"B-{label}" for label in LABELS] + [f"I-{label}" for label in LABELS]

SYSTEM_PROMPT: Final[str] = """\
You are an expert in Natural Language Processing for the Harry Potter universe.
The user will send a JSON object {"tokens": [<token>, ...]}.
Predict one token-level IOB2 label for every token in the input and return
only a JSON object with two fields: "token_labels" and "token_count".

The output MUST satisfy these rules:
- The response must be exactly one JSON object, with no surrounding text.
- The JSON object must contain only the fields "token_labels" and "token_count".
- "token_labels" must be an array of objects, one per input token.
- Each object must have:
  - "token": the exact original token string from the input,
  - "label": the IOB2 tag for that token.
- The "token_labels" array must have exactly the same length as the "tokens" array.
- The "token_count" value must equal the number of tokens in the input.
- If the input has N tokens, return exactly N entries.
- If you are uncertain, label the token as "O" rather than omitting or inventing tags.

Use IOB2-style tags with these short entity codes:
- O
- B-CHAR, I-CHAR
- B-LOC, I-LOC
- B-ORG, I-ORG
- B-SPELL, I-SPELL
- B-CREA, I-CREA
- B-ARTI, I-ARTI

Rules:
- Only label spans that refer to a specific, nameable entity in context.
  Generic references, pronouns, and descriptions do not count.
- Pronouns are never labelled.
- Entities must be referenced, not just implied.
- No nested or overlapping entities.
- Use only the short IOB2 tag strings listed above. Do not return long-form names.
- Do not invent entities.
- If a sentence contains no entities, return exactly one "O" per token.
"""

ENTITY_SCHEMA: Final[dict] = {
    "type": "object",
    "properties": {
        "token_labels": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "token": {"type": "string"},
                    "label": {"type": "string", "enum": IOB_TAGS},
                },
                "required": ["token", "label"],
                "additionalProperties": False,
            },
        },
        "token_count": {
            "type": "integer",
            "minimum": 0,
        },
    },
    "required": ["token_labels", "token_count"],
    "additionalProperties": False,
}
