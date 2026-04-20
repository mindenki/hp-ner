import json
import re
import spacy
from pyunormalize import NFC
import hashlib
from langdetect import detect
from datasketch import MinHash, MinHashLSH



"""
In this step, irrelevant sentences are filtered out from the previously prepared dataset.

  • Minimum 5 and maximum 60 tokens per sentence
  • Parentheses must be balanced ()
  • Only English sentences are kept (currently not working)
  • MinHash deduplication: filters out similar sentences

Finally, each sentence must have a unique ID.
"""

def load_jsonl(path):
    records = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def generate_hybrid_id(i: int, text: str, prefix="hp") -> str:
    """Returns hybrid id for sentences. Might be useful later.\\
        {prefix}-{i:05d}-{h}"""
    h = hashlib.md5(text.encode("utf-8")).hexdigest()[:6]
    return f"{prefix}-{i:05d}-{h}"


def has_balanced_parentheses(text: str) -> bool:
    """Returns True if text has balanced parentheses (RegEx implementation)"""
    s = re.sub(r'[^()]', '', text)
    while re.search(r'\(\)', s):
        s = re.sub(r'\(\)', '', s)
    return not s


def build_minhash(sentence: str) -> MinHash:
    """Returns MinHash value for sentence. Used by deduplicate_senteces."""
    m = MinHash(num_perm=128)
    for token in sentence.split():
        m.update(token.encode("utf-8"))
    return m


def deduplicate_sentences(sentences: list[str], threshold: float = 0.8) -> list[str]:
    """Returns list with senteces to keep. Uses MinHash (build_minhash)"""
    lsh = MinHashLSH(threshold=threshold, num_perm=128)
    deduplicated = []

    for i, sentence in enumerate(sentences):
        m = build_minhash(sentence)
        key = f"s_{i}"

        # If no similar sentence is already in the LSH index, keep it
        if not lsh.query(m):
            lsh.insert(key, m)
            deduplicated.append(sentence)

    return deduplicated


def filter_dataset(input_path, output_path, nlp = spacy.blank("en"), lsh = MinHashLSH(threshold=0.8, num_perm=128)):
    try:
        records = load_jsonl(input_path)
    except FileNotFoundError:
        raise FileNotFoundError(f"Input file not found. Define correct input path (current input path: '{input_path}')") 

    cleaned = []
    dropped = []
    sentence_counter = 1

    for record in records:
        paragraphs = record.get("paragraphs", [])
        for paragraph in paragraphs:
            for sentence in paragraph:
                if not has_balanced_parentheses(sentence):
                    dropped.append({"url": record["url"], "title": record["title"], "sentence": sentence, "reason": "Unbalanced parentheses"})
                    continue

                # if detect(sentence) != "en":
                # dropped.append({"url": record["url"], "title": record["title"], "sentence": sentence, "reason": "Not English"})
                # continue

                tokens = nlp(sentence)
                if len(tokens) < 5 or len(tokens) > 60:
                    dropped.append({"url": record["url"], "title": record["title"], "sentence": sentence, "reason": "Token count"})
                    continue

                m = MinHash(num_perm=128)
                for token in tokens:
                    m.update(token.text.encode("utf-8"))

                if lsh.query(m):
                    continue  # too similar to a sentence already kept

                lsh.insert(generate_hybrid_id(sentence_counter, sentence), m)


                cleaned.append({"id": generate_hybrid_id(sentence_counter, sentence), "text": sentence, "tokens": [token.text for token in tokens], "token_count": len(tokens), "url": record.get("url", ""), "title": record.get("title", "")})
                sentence_counter += 1

    # Save cleaned output
    with open(output_path, "w", encoding="utf-8") as f:
        for record in cleaned:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    return cleaned, dropped


input_path  = "./data/clean/wiki_data_clean.jsonl"
output_path = "./data/clean/wiki_data_filtered.jsonl"

nlp = spacy.blank("en")

cleaned, dropped = filter_dataset(input_path, output_path)

