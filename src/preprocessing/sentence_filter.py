"""Sentence-level filtering for the scraped wiki corpus.

  • Minimum 5 tokens per sentence
  • Parentheses must be balanced ()
  • MinHash deduplication: filters out similar sentences

Each surviving sentence gets a unique ID.
"""
import hashlib
import json
import re

import spacy
from datasketch import MinHash, MinHashLSH

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

                tokens = nlp(sentence)
                if len(tokens) < 5:
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

