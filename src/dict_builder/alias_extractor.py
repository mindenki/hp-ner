""" Scrapes the aliases for canonical names from the Harry Potter wiki. For each cannonical name, fetches the page's infobox. Output: dict: canonical name -> list[alias_string] """
import json
import re
import time
import logging
from pathlib import Path
from bs4 import BeautifulSoup
import requests

logger = logging.getLogger(__name__)

BASE_URL = "https://harrypotter.fandom.com/api.php"
DELAY = .25
MAX_RETRIES = 6
BACKOFF_BASE = 2.0

SESSION = requests.Session()
SESSION.headers.update({
    # set a custom User-Agent to avoid being blocked by the server, and accept gzip encoding for efficiency
    "User-Agent": "hp-ner-dict-builder/1.0 (academic NLP project; contact via GitHub)",
    "Accept-Encoding": "gzip",
})

_ALIAS_KEYS = {
    "alias", "aliases", "also known as", "aka", "nickname", "nicknames",
    "title", "titles", "epithet", "epithets"
}

_SPLIT_RE = re.compile(r"[,\n]|<br\s*/?>|\*|\|", re.IGNORECASE)

STOP_ALIASES = {
    "and", "the", "a", "an", "by", "of", "in"
}

def _get_with_retry(params: dict, delay: float) -> dict | None:
    # same as in category_crawler.py
    """GET with exponential backoff on 429 or 5xx."""
    for attempt in range(MAX_RETRIES):
        try:
            response = SESSION.get(BASE_URL, params=params, timeout=15)
            if response.status_code == 429:
                wait = BACKOFF_BASE ** attempt
                logger.warning(f"[429] rate-limited, waiting {wait:.0f}s (retry {attempt + 1}/{MAX_RETRIES})...")
                time.sleep(wait)  # 😴
                continue
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError:
            if response.status_code >= 500:
                wait = BACKOFF_BASE ** attempt
                logger.warning(f"[5xx] server error, waiting {wait:.0f}s (retry {attempt + 1}/{MAX_RETRIES})...")
                time.sleep(wait)
                continue
            return None
        except (requests.RequestException, ValueError) as e:
            logger.error(f"[error] {e}")
            return None
    logger.error(f"[FAILED] gave up after {MAX_RETRIES} retries")
    return None

def _fetch_infobox_html(page_title: str) -> str | None:
    """Fetch parsed HTML of the page."""
    params = {
        "action": "parse",
        "page": page_title,
        "prop": "text",
        "format": "json",
    }
    raw = _get_with_retry(params, DELAY)
    if not raw:
        logger.warning(f"Failed to fetch HTML for {page_title}")
        return None
    try:
        return raw["parse"]["text"]["*"]
    except KeyError:
        logger.warning(f"No HTML found for {page_title}")
        return None

def _is_valid_alias(alias: str) -> bool:
    if len(alias) < 2:
        return False
    if alias.lower().startswith("ref"):
        return False
    if "http" in alias:
        return False
    if alias.lower() == "unknown":
        return False
    return True

def _clean_alias(text: str) -> str:
    # remove citations like [1]
    text = re.sub(r"\[\d+\]", "", text)
    # remove parentheses refs
    text = re.sub(r"\(.*?citation.*?\)", "", text, flags=re.IGNORECASE)
    # normalize whitespace
    text = re.sub(r"\s+", " ", text)
    return text.strip()

def _strip_explanations(alias: str) -> str:
    # Remove anything starting with '(' until end or closing ')'
    alias = re.sub(r"\(.*?\)", "", alias)  # standard parentheses
    alias = re.sub(r"\(.*$", "", alias)  # leftover open parentheses
    # remove trailing/leading punctuation leftover
    alias = alias.strip(" -,:;")
    return alias.strip()

def _remove_numeric(alias: str):
    if alias.isdigit():
        return None
    if re.fullmatch(r"\d+", alias):
        return None
    return alias

def _remove_stop_alias(alias: str):
    alias_lower = alias.lower().strip()
    if alias_lower in STOP_ALIASES:
        return None
    # remove alias starting with stopwords
    if any(alias_lower.startswith(w + " ") for w in STOP_ALIASES):
        return None
    return alias

def _normalize_alias(alias: str):
    alias = _strip_explanations(alias)
    if not alias:
        return None
    # remove citations like [1]
    alias = re.sub(r"\[\d+\]", "", alias)
    alias = alias.strip()
    alias = _remove_numeric(alias)
    if not alias:
        return None
    alias = _remove_stop_alias(alias)
    if not alias:
        return None
    if not _is_valid_alias(alias):
        return None
    # finally remove leftover fragments shorter than 2 chars
    if len(alias) < 2:
        return None
    return alias

def _generate_person_short_forms(name: str) -> list[str]:
    parts = name.split()
    if len(parts) < 2:
        return []
    generated = set()
    def add(part):
        if len(part) < 4:
            return
        if not part.isalpha():
            return
        if not part[0].isupper():
            return
        generated.add(part)
        if part.endswith("s"):
            generated.add(part + "'")
        else:
            generated.add(part + "'s")
    add(parts[0])  # first
    add(parts[-1])  # last
    return list(generated)

def _extract_aliases(html: str) -> list[str]:
    """Extract aliases from PortableInfobox HTML."""
    soup = BeautifulSoup(html, "html.parser")
    infobox = soup.find("aside", class_="portable-infobox")  # the main infobox container, may not exist for some pages
    if not infobox:
        return []
    aliases = []
    for row in infobox.find_all("div", class_="pi-data"):  # each row of the infobox is a div with class "pi-data"
        label = row.find("h3")  #
        if not label:
            continue
        key = label.text.strip().lower()
        if key not in _ALIAS_KEYS:
            continue
        value = row.find("div", class_="pi-data-value")
        if not value:
            continue
        # aliases are often separated by <br>
        parts = list(value.stripped_strings)
        for part in parts:
            part = _clean_alias(part)
            alias = _normalize_alias(part)
            if not alias:
                continue
            aliases.append(alias)
    return list(set(aliases))

def scrape_aliases_for_label(names: list[str], label: str) -> dict[str, list[str]]:
    """Given a list of canonical names for a specific label, scrape their aliases from the wiki."""
    result = {}
    total = len(names)
    number_of_aliases = 0
    for i, name in enumerate(names, 1):
        if i % 10 == 0:
            logger.info(f"{label}: Processing {i}/{total} - {name}")
        logger.info(f"{label}: Found {number_of_aliases} aliases so far for {i} names.")
        html = _fetch_infobox_html(name)
        if not html:
            result[name] = []
        else:
            aliases = _extract_aliases(html)
            aliases = [a for a in aliases if _is_valid_alias(a)]
            aliases = [
                a for a in aliases
                if a.lower() != name.lower()
            ]
            if label == "CHAR":  # for characters, also add first/last name forms if they are not too common
                aliases.extend(_generate_person_short_forms(name))
                # full name possessive
                if name.endswith("s"):
                    aliases.append(name + "'")
                else:
                    aliases.append(name + "'s")
            aliases = list(set(aliases))
            aliases.sort()
            logger.info(f"{label}: Extracted aliases for '{name}': {aliases}")
            result[name] = aliases
            number_of_aliases += len(aliases)
        time.sleep(DELAY)  # be polite and avoid hammering the server 😴
    found = sum(1 for v in result.values() if v)
    found_total = sum(len(a) for a in result.values())
    logger.info(f"{label}: Found aliases for {found}/{total} names, total {found_total} aliases.")
    return result

def scrape_all_labels(canonical_dict: dict[str, list[str]]) -> dict[str, dict[str, list[str]]]:
    """Scrape aliases for all labels in the canonical dict."""
    aliases_path = Path("data/dictionaries/hp_aliases.json")
    aliases_path.parent.mkdir(parents=True, exist_ok=True)
    if aliases_path.exists():
        logger.info(f"Found existing alias cache at {aliases_path}, loading...")
        cache = json.loads(aliases_path.read_text(encoding="utf-8"))
    else:
        cache = {}
    for label, names in canonical_dict.items():
        if label in cache:
            logger.info(f"Using cached aliases for label '{label}'...")
            continue
        logger.info(f"Scraping aliases for label '{label}'...")
        cache[label] = scrape_aliases_for_label(names, label)
        # Save after each label to avoid losing progress
        aliases_path.write_text(json.dumps(cache, indent=2, ensure_ascii=False), encoding="utf-8")
        logger.info(f"{label}: Saved aliases to cache.")
    return cache