""" Merges dict and BERT IOB2 tag sequentes to produce silver labels for training.

    PRESEDENCE RULES:
        - SPELL/ARTIFACT/CREATURE  -> dict always wins as BERT cannot predict these
        - CHARACTER/LOCATION/ORGANIZATION -> if one labels as entity, the other does not -> take the entity label
        Conflict(same span, different entity) -> bert wins
        
silver_source tracks per-token provenance: 'dict', 'bert', 'both or 'O'.

"""

import logging 

logger = logging.getLogger(__name__)

DICT_ONLY_LABELS = {"SPELL", "ARTI", "CREA"}


def _get_label(tag: str) -> str:
    """ Extracts the label from a BERT tag, e.g. 'B-CHAR' -> 'CHAR'. """
    if tag == "O":
        return "O"
    return tag.split("-")[1]

def merge(dict_tags: list[str], bert_tags: list[str], conflict_counts: dict[str, int]) -> tuple[list[str], list[str], int]:
    """ 
    Merges the dict_tags and bert_tags according to the precedence rules.
    Also updates conflict_counts with any conflicts encountered.
    
    Returns: (merged_tags, source_tags, number_of_conflicts) source is either dict, bert, or O.
    """
    
    number_of_conflicts = 0
    merged = []
    sources = []
    
    
    for d_tag, b_tag in zip(dict_tags, bert_tags):
        d_label = _get_label(d_tag)
        b_label = _get_label(b_tag)
    
        has_dict = d_label != "O"
        has_bert = b_label != "O"
        # SPELL/ARTI/CREA -> dict always wins
        if d_label in DICT_ONLY_LABELS:
            merged.append(d_tag)
            sources.append("dict")
            continue
        
        # Both 0 -> 0
        if not has_dict and not has_bert:
            merged.append("O")
            sources.append("O")
            continue
        
        # only one labels as entity -> take that one
        if has_dict and not has_bert:
            # but if its a character, we will let not label it
            merged.append("O" if d_label == "CHAR" else d_tag)
            sources.append("dict")
            continue
        
        if not has_dict and has_bert:
            merged.append(b_tag)
            sources.append("bert")
            continue
        
        
        # Both label as entity 
    
        # they agree; put both 
        if d_label == b_label:
            merged.append(d_tag)
            sources.append("both")
        # they conflict; dict wins but count the conflict
        
        else:
            number_of_conflicts += 1
            conflict_counts[f"{b_label}->{d_label}"] = conflict_counts.get(f"{b_label}->{d_label}", 0) + 1
            merged.append(b_tag)
            sources.append("bert")
            
    return merged, sources, number_of_conflicts


def iob2_to_spans(tags: list[str]) -> list[tuple[int,int,str]]:
    """Convert IOB2 tag list to (start, end_exclusive, label) spans."""
    spans = []
    start = None
    current_label = None
    
    
    
    for i, tag in enumerate(tags):
        if tags[i].startswith("B-"):
            if start is not None:
                spans.append((start, i, current_label))
            start = i
            current_label = tag[2:]
        elif tags[i].startswith("I-"):
            label = tag[2:]
            if start is  None or label != current_label:
                if start is not None:
                    spans.append((start, i, current_label))
                start = i
                current_label = label
        else: # O tag
            if start is not None:
                spans.append((start, i, current_label))
            start = None
            current_label = None
            
    if start is not None:
        spans.append((start, len(tags), current_label))
        
    return spans