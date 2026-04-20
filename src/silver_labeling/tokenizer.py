""" 

SHared tokenizer for silver labeling, that will be used by both our model and the dictionary-based silver labeling. 

spaCy will handle punctuation splitting cleanly which will help the dict matchings.

Both taggers receive the same tokenizations, and later on will be be merged in a simple zip.

"""



import logging
import spacy
from spacy.cli import download as spacy_download

from functools import lru_cache

logger = logging.getLogger(__name__)

def _load_spacy_model(name: str, **kwargs):
    try:
        return spacy.load(name, **kwargs)
    except OSError:
        logger.info("Model '%s' not found — downloading...", name)
        spacy_download(name)
        return spacy.load(name, **kwargs)

class Tokenizer:
    """ 
    spaCy tokenizer wrapper.
    Returns a list of tokens.
    """

    def __init__(self):
        self._nlp = _load_spacy_model("en_core_web_sm", disable=["parser", "ner", "lemmatizer", "attribute_ruler"])
        logger.info("Loaded spaCy tokenizer.")
    
    
    def tokenize(self, text: str) -> list[str]:
        """ Tokenizes the input text and returns list of tokens."""
        doc = self._nlp(text) # doc is a spacy Doc object which contains the tokens and their attributes(like start and end char offsets)
        return [token.text for token in doc] # we only need the str of the tokens
    
    def tokenize_batch(self, texts: list[str]) -> list[list[str]]:
        """ efficient batch tokenization using spaCy's pipe method."""
        docs = self._nlp.pipe(texts, batch_size=256) # this is much faster than calling tokenize on each text individually, especially for large batches
        return [[token.text for token in doc] for doc in docs]
    
    