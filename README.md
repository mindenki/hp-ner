Entity Dictionaries + Silver Labeling

- Build gazetteer lists for all 6 types: CHARACTER, LOCATION, ORGANIZATION, CREATURE, SPELL, ARTIFACT
- Source: Fandom wiki infoboxes + category pages; deduplicate & normalize casing
- Silver labeling: run dslim/bert-base-NER on filtered sentences; map CoNLL labels → HP schema
- Merge BERT predictions with dict lookup for SPELL/ARTIFACT/CREATURE (higher precision)