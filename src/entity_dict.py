"""
Loads the entity dictionaries from *.txt files in the data directory.
It provides greedy longest match lookup for entities in a given text.
Lookup is case-insensitive, longest match wins.

––––––––––––––––––––––––
The format of the txts:
    Harry Potter
    > The Boy Who Lived 
    > The Chosen One
    Ron Weasley
Aliases prefixed with '>'
––––––––––––––––––––––––
"""


import logging
import os
import re
from dataclasses import dataclass

logger = logging.getLogger(__name__)


ENTITY_TYPES = ["character", "location", "organization", "spell", "creature", "artifact"]


@dataclass
class DictMatch: # stores the result of a match
    entity_type: str
    canonical_name: str
    start: int # index of the start of the match in the text
    end: int # index of the end of the match in the text( exclusive)
    


class EntityDictionary:
    """
    Loads entity dictionaries from the txt files for all 6 entity types.
    Performs greedy longest match lookup for entities in a given text. 
    It means that if there are multiple matches for a substring, it will return the longest one.
    """
    
    def __init__(self, dict_dir: str):
        self.dict_dir = dict_dir
        self._lookup: dict[str, tuple[str,str]] = {} # this maps lowercase entity names to (canonical name, entity type)
        self._load_dicts()
    
    

    def _load_dicts(self) -> None:
        """Loads the entity dictionaries from the txt files for all entity types."""
        total = 0
        total_loaded = len(ENTITY_TYPES)
        for entity_type in ENTITY_TYPES:
            path = os.path.join(self.dict_dir, f"{entity_type}.txt")
            if not os.path.exists(path):
                logger.warning(f"Dictionary file for {entity_type} not found at {path}. Skipping.")
                total_loaded -= 1
                continue
            count = self._load_file(path, entity_type)
            logger.info(f"Loaded {count} entries for {entity_type} from {path}.")
            total += count
        logger.info(f"Total {total} entries loaded across {total_loaded} entity types.")
        
    def _load_file(self, path: str, entity_type: str) -> int:
        """ Loads a single dictionary file and updates the lookup dictionary. Returns the number of entries loaded."""
        count = 0
        current_canonical = None
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line: # empty line, skip
                    continue
                if line.startswith(">"): # this is an alias
                    alias = line[1:].strip() # we dont need the '>' prefix
                    if current_canonical and alias: # neither is empty
                        self._lookup[alias.lower()] = (current_canonical, entity_type)
                        count += 1
                else: # this is a canonical name
                    current_canonical = line
                    self._lookup[current_canonical.lower()] = (current_canonical, entity_type)
                    count += 1
        return count

    def match(self, words: list[str]) -> list[DictMatch]:
        """

        Performs greedy longest match lookup for entities in the given list of words.
        Returns non-overlapping DictMatch objects sorted by start index.
        """

        matches = []
        i = 0
        n = len(words)
 
        while i < n:
            best_match = None
            best_len = 0
            
            for j in range(min(n, i + 10), i, -1):  # max 10-token span
                span = " ".join(words[i:j]).lower()
                if span in self._lookup:
                    canonical, entity_type = self._lookup[span]
                    if j - i > best_len:
                        best_match = DictMatch(
                            entity_type=entity_type,
                            canonical=canonical,
                            start=i,
                            end=j,
                        )
                        best_len = j - i
 
            if best_match:
                matches.append(best_match)
                i = best_match.end  # skip past matched span
            else:
                i += 1
        return matches
    
def matches_to_bio(self, words: list[str], matches: list[DictMatch]) -> list[str]:
    """Converts the matches to BIO format labels for each words in the input text."""
    labels = ["O"] * len(words)
    for match in matches:
        labels[match.start] = f"B-{match.entity_type.upper()}"
        for i in range(match.start + 1, match.end):
            labels[i] = f"I-{match.entity_type.upper()}"
    return labels
       
                    
                    
                    
                    