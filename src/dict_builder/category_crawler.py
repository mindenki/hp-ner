"""
HP Fandom category crawler

Fetches only page members of the categories defined in categories.py, which are manually curated to 
avoid bleeding into unrelated domains. 
"""

import time
import requests
import logging
from pathlib import Path
import json

logger = logging.getLogger(__name__)



BASE_URL = "https://harrypotter.fandom.com/api.php"
DELAY = 0.25 # seconds between requests to avoid rate-limiting
MAX_RETRIES = 6
BACKOFF_BASE = 2.0

SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": "hp-ner-dict-builder/1.0 (academic NLP project; contact via GitHub)",
    "Accept-Encoding": "gzip",
}) # Use a session to reuse connections and set a custom User-Agent to avoid being blocked by the server.



def _get_with_retry(params: dict, delay: float) -> dict | None:
    """GET with exponential backoff on 429 or 5xx. Returns JSON or None."""
    for attempt in range(MAX_RETRIES):
        try:
            response = SESSION.get(BASE_URL, params=params, timeout=15)

            if response.status_code == 429:
                wait = BACKOFF_BASE ** attempt
                logger.warning("[429] rate-limited, waiting %.0fs (retry %d/%d)", wait, attempt + 1, MAX_RETRIES)
                time.sleep(wait)
                continue

            response.raise_for_status()
            return response.json()

        except requests.exceptions.HTTPError:
            if response.status_code >= 500:
                wait = BACKOFF_BASE ** attempt
                logger.warning("[5xx] server error, waiting %.0fs (retry %d/%d)", wait, attempt + 1, MAX_RETRIES)
                time.sleep(wait) # 😴
                continue
            return None
        except (requests.RequestException, ValueError) as e:
            logger.error("[error] %s", e)
            return None

    logger.error("[FAILED] gave up after %d retries", MAX_RETRIES)
    return None




def crawl_category_members(category: str, delay: float = DELAY) -> list[str]:
    """ Fetch all the page members of a given category(shallow, no subcategories)
    Args:
        category: The name of the category to fetch members for(without "Category:" prefix).
        delay: Seconds to sleep between paginated requests.
    Returns:
        Sorted list of page titles.
    """
    
    members = []
    params = {
        "action": "query",
        "list": "categorymembers", # API endpoint to fetch category members
        "cmtitle": f"Category:{category}", 
        "cmlimit": 500, # Max limit per request
        "cmtype": "page", # Only fetch pages, not subcategories or files
        "format": "json",
    }
    
    while True:
        data = _get_with_retry(params, delay)
        if data is None or "query" not in data:
            break

        members.extend(m["title"] for m in data["query"]["categorymembers"])

        if "continue" in data:
            params["cmcontinue"] = data["continue"]["cmcontinue"]
            time.sleep(delay)
        else:
            break

    return sorted(set(members))
       
        
            
            
def crawl_all(categories: dict[str, list[str]], delay: float=DELAY) -> dict[str, list[str]]:
    """ Crawl all categories for every label and return uncleaned results.
    
    Args:
        categories: Label → list-of-category-names mapping (from categories.py).
        delay: Seconds to sleep between paginated requests.
    Returns:
        Label → sorted list of page titles (may contain noise, cleaned later).
        
    """
    
    results = {label: set() for label in categories}
    
    
    for label, cats in categories.items():
        for cat in cats:
            logger.info(f"Crawling category '{cat}' for label '{label}'...")
            members = crawl_category_members(cat, delay)
            logger.info(f"Found {len(members)} members in category '{cat}'.")
            results[label].update(members)
            time.sleep(delay) # 😴
    final = {label: sorted(members) for label, members in results.items()}

    out_path = Path("data/dictionaries/hp_raw.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(final, indent=2, ensure_ascii=False), encoding="utf-8")
    logger.info(f"Raw crawl saved to {out_path}")

    return final
