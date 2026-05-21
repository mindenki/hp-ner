import openai
import os
import logging
import asyncio
from tenacity import retry, wait_exponential, stop_after_attempt, retry_if_exception
import json
from pathlib import Path


logging.basicConfig(level=logging.INFO, format=' %(asctime)s - %(levelname)s - %(message)s')

OPENAI_MODEL = "gpt-4o"
client = openai.AsyncOpenAI(api_key=os.environ.get("OPENAI_API_KEY", "KEY"))
MAX_CONCURRENT_REQUESTS = 5 
semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)


SYSTEM_PROMPT = """You are an expert in Natural Language Processing for the Harry Potter Universe.
Identify entities of the following types in the user's sentence.


    Character: Any named individual — human, wizard, ghost, or non-human being 
    — who is treated as a specific person with an identity. T
    his includes real-world people appearing in the text. Note on titles: 
    When a title and name appear together, annotate the full span including the title. (e.g., "Harry Potter", "the Chosen One")

    Location: Any named place — real or fictional — including buildings, rooms, regions, countries, and geographical features.(e.g., "Hogwarts", "Diagon Alley")

    Organization: Any named real or fictional group, institution, team, or structured body, including government bodies, 
    named movements, publications as organizations and Events with an organizing comittee(e.g., "Death Eaters", "Order of the Phoenix")

    Spell: Any named magical incantation, charm, curse, hex, jinx, counterspell, or a named spell category. 
    Potions are not included here. (e.g., "Killing Curse", "Expecto Patronum")

    Creature: Any named magical creature, non-human species, or individual animal that does not qualify as a CHARACTER, 
    including named species, named pets and magical plants which bear human features.(e.g., "Dementor", "Niffler")

    Artifact: Any named magical object, item, potion, book, or artefact. This includes potions, Horcruxes, 
    named vehicles and weapons, and the Deathly Hallows.(e.g., "Horcrux", "Elder Wand")

Rules:
    -Only label a word when it is actually referring to a specific, nameable entity in context. Generic references, pronouns, and descriptions do not count.
    -Pronouns are never labelled.
    -Entities must be referenced, not just implied.
    -No nested entities are allowed.
    -Only return entities whose text appears verbatim in the input.
    - Use token offsets (0-indexed, end-exclusive).
    - Return spans in this format: {"labels": [[start, end, label]]}
    - Do not invent entities; if a sentence contains none, return an empty list."""

    
ENTITY_SCHEMA = {
    "type": "object",
    "properties": {
        "labels": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "start": {"type": "integer"},
                    "end": {"type": "integer"},
                    "label": {
                        "type": "string",
                        "enum": [
                            "Character",
                            "Location",
                            "Organization",
                            "Creature",
                            "Spell",
                            "Artifact"
                        ]
                    }
                },
                "required": ["start", "end", "label"],
                "additionalProperties": False
            }
        }
    },
    "required": ["labels"],
    "additionalProperties": False
}
    

def is_retryable(exception):
    if isinstance(exception, openai.RateLimitError):
        return True
    if isinstance(exception, openai.APIStatusError) and exception.status_code >= 500:
        return True
    return False

@retry(wait=wait_exponential(min=1, max=10), stop=stop_after_attempt(5), retry=retry_if_exception(is_retryable))
async def run_openai_task(tokens:list[str]):
    async with semaphore:
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",
            "content": json.dumps({"tokens": tokens})
            }
        ]

        response = await client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=messages, 
            temperature=0,
            seed=42,
            response_format= {
                "type": "json_schema",
                "json_schema": {
                    "name": "ner",
                    "schema": ENTITY_SCHEMA,
                    "strict": True}})

        return json.loads(response.choices[0].message.content)

def convert_labels(result):
    return [
        [e["start"], e["end"], e["label"]]
        for e in result["labels"]
    ]

async def run_and_save(sentence, f) -> dict:
    result = await run_openai_task(sentence)
    entry = {
    "tokens": sentence,
    "labels": convert_labels(result)
}
    f.write(json.dumps(entry) + "\n")
    f.flush()
    return result

async def annotate(sentences: list) -> list[dict]:
    Path("outputs").mkdir(parents=True, exist_ok=True)
    with open("outputs/predictions_good.jsonl", "a") as f:
        tasks = [run_and_save(sentence, f) for sentence in sentences]
        results = await asyncio.gather(*tasks)
    return results

sentences = [["It", "was", "planted", "in", "1971", "to", "disguise", "the", "opening", "of", "a", "secret", "passage", "leading", "from", "the", "Hogwarts", "grounds", "to", "the", "Shrieking", "Shack", ",", "a", "building", "located", "in", "the", "village", "of", "Hogsmeade", "."], ["Nymphadora", "Tonks", "also", "had", "a", "hare", "patronus", ",", "specifically", "in", "the", "form", "of", "a", "Jack", "Rabbit", ",", "until", "her", "growing", "love", "for", "Remus", "Lupin", ",", "a", "werewolf", ",", "in", "1996", "resulted", "in", "it", "changing", "to", "a", "wolf", "."], ["Germany", "is", "a", "republic", "in", "central", "Europe", "."], ["Professor", "Binns", "had", "a", "copy", "in", "his", "classroom", "in", "Hogwarts", "Castle", "."], ["This", "led", "to", "a", "lifelong", "fear", "of", "them", ",", "which", "drove", "her", "to", "request", "that", "the", "British", "Ministry", "of", "Magic", "humanely", "eradicate", "the", "pixie", "species", "."]]

asyncio.run(annotate(sentences))








