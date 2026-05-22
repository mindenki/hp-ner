import json
import logging
import re
from pyunormalize import NFC
import spacy

logger = logging.getLogger(__name__)


def load_jsonl(path):
    records = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def is_valid_record(record):
    paragraphs = record.get("paragraphs", [])

    # Drop records with no paragraphs at all
    if not paragraphs:
        return False, "empty paragraphs list"

    # Drop if every paragraph is blank
    if not any(p.strip() for p in paragraphs):
        return False, "all paragraphs empty"

    return True, None


def sentencizer(text):
    doc = nlp(text)

    return [sent.text for sent in doc.sents]


def clean_paragraph(paragraph):
    # NFC normalization
    paragraph = NFC(paragraph)

    # Unicode character replacements
    paragraph = paragraph.replace("\u2013", "-")
    paragraph = paragraph.replace("\u2014", "-")
    paragraph = paragraph.replace("\u2018", "'")
    paragraph = paragraph.replace("\u2019", "'")
    paragraph = paragraph.replace("\u201c", '"')
    paragraph = paragraph.replace("\u201d", '"')
    paragraph = paragraph.replace("\u2026", "...")
    paragraph = paragraph.replace("\u00a0", " ")
    paragraph = paragraph.replace("\u2060", "")

    # Wiki markup
    paragraph = re.sub(r"\[\s*citation needed\s*\]", "", paragraph, flags=re.IGNORECASE)

    # Whitespace cleanup
    paragraph = re.sub(r" {2,}", " ", paragraph)
    paragraph = paragraph.strip()

    return paragraph


def clean_record(record):
    cleaned_paragraphs = []

    for paragraph in record["paragraphs"]:
        # Skip empty paragraphs
        if not paragraph.strip():
            continue
 
        cleaned_paragraphs.append(sentencizer(clean_paragraph(paragraph)))

    return {**record, "paragraphs": cleaned_paragraphs}


def clean_dataset(input_path, output_path):
    try:
        records = load_jsonl(input_path)
    except FileNotFoundError:
        raise FileNotFoundError(f"Input file not found te kis csacsi. Define correct input path (current input path: '{input_path}')") 

    cleaned = []
    dropped = []

    for record in records:
        # Step 1: validate
        valid, reason = is_valid_record(record)
        if not valid:
            dropped.append({"url": record["url"], "title": record["title"], "reason": reason})
            continue

        # Step 2: clean each paragraph in the list
        cleaned.append(clean_record(record))

    # Save cleaned output
    with open(output_path, "w", encoding="utf-8") as f:
        for record in cleaned:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    return cleaned, dropped


nlp = spacy.blank("en")
nlp.add_pipe("sentencizer")


input_path  = "input path (wiki_data.jsonl)"
output_path = "output path (wiki_data_clean.jsonl)"

cleaned, dropped = clean_dataset(input_path, output_path)

logger.info("Kept:    %s records", len(cleaned))
logger.info("Dropped: %s records", len(dropped))

if dropped:
    logger.info("Dropped records:")
    for d in dropped:
        logger.info("  '%s' -> %s", d['title'], d['reason'])

logger.debug("Sample cleaned output:")
for record in cleaned[:3]:
    logger.debug("[%s]", record['title'])
    for p in record["paragraphs"][:2]:
        logger.debug("  %s", p)