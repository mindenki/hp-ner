# HP-NER Annotation Guidelines

**Project:** Harry Potter Named Entity Recognition (HP-NER)  
**Annotators:** Hanna, Zita, Anis, Peter  
**Version:** 1.0  
**Last updated:** April 2026

---

## Table of Contents

1. [What is Named Entity Recognition?](#1-what-is-named-entity-recognition)
2. [General Annotation Rules](#2-general-annotation-rules)
3. [The 6 Entity Types](#3-the-6-entity-types)
   - [CHARACTER](#character-char)
   - [LOCATION](#location-loc)
   - [ORGANIZATION](#organization-org)
   - [SPELL](#spell-spell)
   - [CREATURE](#creature-crea)
   - [ARTIFACT](#artifact-arti)
4. [Span Boundaries](#4-span-boundaries)
5. [IOB2 Format](#5-iob2-format)
6. [Handling Silver Pre-Annotations](#6-handling-silver-pre-annotations)
7. [Annotation Workflow](#7-annotation-workflow)
8. [Per-Annotator Focus Areas](#8-per-annotator-focus-areas)
9. [Adjudication](#9-adjudication)
10. [Quick Reference](#10-quick-reference)

---

## 1. What is Named Entity Recognition?

Named Entity Recognition (NER) is the task of identifying and classifying **specific named entities** in text — things like people, places, and organizations — by labelling each token with a category.

The key principle is: **we only label a word when it is actually referring to a specific, nameable entity in context.** Generic references, pronouns, and descriptions do not count.

### Core NER principles

**Only label when the word refers to a specific entity:**
> *"The wizard cast a spell."* → nothing to label  
> *"Harry cast Expelliarmus."* → `Harry` = CHAR, `Expelliarmus` = SPELL

**Pronouns are never labelled:**
> *"She ran to Hogwarts."* → `Hogwarts` = LOC, but `She` = nothing

**Possessive context does not make the possessor an entity:**
> *"Peter's dog barked."* → `Peter` here is just establishing ownership of the dog — if Peter is not the focus of the sentence and appears only as a possessive modifier, do not label him.  
> *"Peter ran into the room."* → `Peter` = CHAR (he is the subject, the entity in focus)

> ⚠️ **Rule of thumb:** Ask yourself — *"Is this word referring to a specific named entity that is relevant to the sentence?"* If the answer is no, do not label it.

**Entities must be referenced, not just implied:**
> *"The Headmaster spoke."* → the Headmaster is not named here — no label  
> *"Dumbledore spoke."* → CHAR

---

## 2. General Annotation Rules

### Real-world vs. in-universe entities

You should label **all named entities**, not just Harry Potter ones. Real-world people, places, and organizations that appear in the text are also valid entities.

> *"He read about Napoleon in the library."* → `Napoleon` = CHAR  
> *"She found an article from the BBC."* → `BBC` = ORG  
> *"They flew over London."* → `London` = LOC

The entity types still apply — use your judgment based on what the entity *is*, not whether it is from the HP universe.

### Articles and determiners in spans

In general, **do not include `the`, `a`, `an`** at the start of an entity span unless the article is grammatically part of the established proper name.

| Text | Annotate |
|------|----------|
| `the Death Eaters` | `Death Eaters` only |
| `the Ministry of Magic` | `Ministry of Magic` only |
| `The Hague` | `The Hague` — the article is part of the name |
| `the Elder Wand` | `Elder Wand` only |
| `a Dementor appeared` | `Dementor` only |

> **Rule:** If removing `the` still leaves a valid proper name, do not include it. If the name is never used without `the` (e.g., `The Hague`, `The Beatles`), include it.

### Consistency across the document

Once you decide how to label an entity in one sentence, apply the same decision throughout your annotation file. If you change your mind, go back and update previous occurrences.

---

## 3. The 6 Entity Types

---

### CHARACTER (`CHAR`)

Any **named individual** — human, wizard, ghost, or non-human being — who is treated as a specific person with an identity. This includes real-world people appearing in the text.

**Note on titles:** When a title and name appear together (`Professor Dumbledore`, `Lord Voldemort`, `Minister Fudge`), annotate the **full span including the title** — the title is part of how the character is addressed and identifying them by title+name is a single reference.

✅ **Include:**
- Full names: `Harry Potter`, `Hermione Granger`, `Albus Dumbledore`
- Title + name together: `Professor Dumbledore`, `Lord Voldemort`, `Minister Fudge`
- First names when clearly referential: `Hermione` when it clearly refers to Hermione Granger
- Established nicknames: `The Boy Who Lived`, `Mad-Eye`, `the Dark Lord`, `You-Know-Who`
- Ghosts: `Nearly Headless Nick`, `Moaning Myrtle`, `the Bloody Baron`
- Portrait subjects referred to as individuals: `Phineas Nigellus`
- Historical and mythological figures: `Merlin`, `Morgan le Fay`
- Real-world people: `Napoleon`, `Shakespeare`, `Queen Victoria`
- Named non-human individuals who are treated as people with personality and narrative agency (see CREA boundary below): `Dobby`, `Griphook`, `Firenze`

❌ **Exclude:**
- Generic role descriptions: `the witch`, `a wizard`, `the professor`, `an Auror`
- Pronouns: `he`, `she`, `they`, `him`
- Relational descriptions without a name: `Harry's aunt`, `a Death Eater`, `the old man`
- House names referring to groups of students (use ORG): `the Gryffindors`

**Tricky cases:**

| Text | Decision | Reason |
|------|----------|--------|
| `Professor Dumbledore` | CHAR — full span | Title + name together = one entity reference |
| `Professor` alone | ❌ | Too generic |
| `the Chosen One` | CHAR | Established nickname for Harry Potter |
| `the Dark Lord` | CHAR | Established nickname for Voldemort |
| `He-Who-Must-Not-Be-Named` | CHAR | Established nickname |
| `Gryffindor` in "he was a Gryffindor at heart" | CHAR | Refers to Godric Gryffindor or the ideal |
| `Gryffindor` in "Gryffindor won the Cup" | ORG | Refers to the house as a group |
| `Dumbledore's Army` | ORG | Named group — see ORG |
| `Dobby` | CHAR | Named individual with personality and narrative agency |
| `Griphook` | CHAR | Named individual goblin with agency |
| `Firenze` | CHAR | Named centaur with individual role |

---

### LOCATION (`LOC`)

Any **named place** — real or fictional — including buildings, rooms, regions, countries, and geographical features.

✅ **Include:**
- Named buildings and areas: `Hogwarts` (as place/grounds), `Azkaban`, `Diagon Alley`, `Hogsmeade`
- Named rooms: `the Great Hall`, `the Room of Requirement`, `the Chamber of Secrets`
- Named natural features: `the Forbidden Forest`, `the Black Lake`, `the Astronomy Tower`
- Countries and cities: `England`, `London`, `Edinburgh`, `Godric's Hollow`
- Real-world locations: `Paris`, `New York`, `the Amazon`
- Magical regions and hidden places: `Knockturn Alley`, `the Ministry Atrium`

❌ **Exclude:**
- Generic location words: `the forest`, `a room`, `the school`, `a nearby town`
- Event names that contain a place: `the Battle of Hogwarts` is an event — annotate `Hogwarts` as LOC only if it appears separately
- Directional references: `upstairs`, `the left corridor`

**LOC vs ORG — the Hogwarts rule:**

This is the most common ambiguity. Use context to decide:

| Usage | Label | Signal |
|-------|-------|--------|
| `She walked through Hogwarts` | LOC | Spatial movement |
| `Hogwarts accepted her` | ORG | Institutional action |
| `the halls of Hogwarts` | LOC | Physical space |
| `Hogwarts has strict rules` | ORG | Institution with policies |
| `Hogwarts School of Witchcraft and Wizardry` | ORG | Full institutional name |

**Tricky cases:**

| Text | Decision | Reason |
|------|----------|--------|
| `Hogwarts` (spatial) | LOC | |
| `Hogwarts School of Witchcraft and Wizardry` | ORG | Full institutional name |
| `Ministry of Magic` (institution) | ORG | |
| `Ministry corridors` | LOC | Physical space |
| `Gryffindor Tower` | LOC | Named physical location |
| `the Battle of Hogwarts` | ❌ (event) | Not a place — `Hogwarts` standalone = LOC |
| `the Department of Mysteries` | ORG | Named department = institution |

---

### ORGANIZATION (`ORG`)

Any **named group, institution, team, or structured body** — real or fictional.

✅ **Include:**
- Schools as institutions: `Hogwarts School of Witchcraft and Wizardry`, `Beauxbatons`, `Durmstrang`
- Government bodies: `the Ministry of Magic`, `the Wizengamot`, `MACUSA`
- Named groups and movements: `the Order of the Phoenix`, `Dumbledore's Army`, `Death Eaters`
- Sports teams: `the Holyhead Harpies`, `Chudley Cannons`
- Named clubs and societies: `the Slug Club`, `S.P.E.W.`, `the Inquisitorial Squad`
- Publications as organizations: `the Daily Prophet` (when referring to the outlet)
- Real-world organizations: `the BBC`, `the United Nations`, `Twitter`
- Businesses: `Gringotts`, `Ollivanders`

❌ **Exclude:**
- Unnamed groups: `a group of wizards`, `the students`, `some Aurors`
- Generic collective nouns: `the professors`, `the Death Eater forces` (but `Death Eaters` = ORG)

**Tricky cases:**

| Text | Decision | Reason |
|------|----------|--------|
| `Death Eaters` | ORG | Named group |
| `a Death Eater` (singular generic) | ❌ | Not a named entity in this usage |
| `the Marauders` | ORG | Named group |
| `the Auror Office` | ORG | Named department |
| `Gringotts` | ORG | Named institution |
| `S.P.E.W.` | ORG | Named society |
| `the Daily Prophet` (outlet) | ORG | |
| `a copy of the Daily Prophet` | ARTI | Physical object |

---

### SPELL (`SPELL`)

Any **named magical incantation, charm, curse, hex, jinx, or counterspell**. Potions are **not** included here — they are ARTIFACT (see below).

**Why exclude potions?** Spells are incantations or named magical effects — actions performed with a wand or through intent. Potions are physical objects that are brewed and consumed — they belong to the ARTIFACT category, which covers magical objects and items.

**On named spell categories (e.g., "the Unforgivable Curses"):** Named categories of spells with an established canonical name should be labelled as SPELL — but be conservative. Only label them if the category name itself is the thing being referred to, not just a generic description.

| Text | Decision |
|------|----------|
| `the Unforgivable Curses` | SPELL — established named category |
| `an Unforgivable` | SPELL — shorthand for the category |
| `dark curses` | ❌ — generic description |
| `a hex` | ❌ — generic |

✅ **Include:**
- Incantations: `Expelliarmus`, `Avada Kedavra`, `Wingardium Leviosa`, `Accio`
- Named spells without incantations: `the Killing Curse`, `the Patronus Charm`, `the Imperius Curse`
- Named spell categories: `the Unforgivable Curses`, `the Cheering Charm`
- Named magical contracts and enchantments: `the Fidelius Charm`, `the Unbreakable Vow`

❌ **Exclude:**
- Potions of any kind → these are **ARTIFACT**
- Generic descriptions: `a curse`, `a spell`, `some magic`, `a charm`
- The word `magic` alone
- Descriptions of magical actions without an established name: `waved his wand`, `cast a shield`

**Tricky cases:**

| Text | Decision | Reason |
|------|----------|--------|
| `Expelliarmus` | SPELL | |
| `the Patronus Charm` | SPELL | Named charm |
| `a Patronus appeared` | CREA | The creature produced, not the spell |
| `the Cruciatus` | SPELL | Shorthand for Cruciatus Curse |
| `the Unforgivable Curses` | SPELL | Named canonical category |
| `Polyjuice Potion` | ARTI | Potion = artifact |
| `Veritaserum` | ARTI | Potion = artifact |
| `Felix Felicis` | ARTI | Potion = artifact |

---

### CREATURE (`CREA`)

Any **named magical creature, non-human species, or individual animal** that does not qualify as a CHARACTER.

**Why are named creatures in CREA and not CHAR?**  
The CHAR category is reserved for entities treated as *people* — individuals with names, personalities, and full narrative agency comparable to a human character. Creatures like `Buckbeak` and `Fawkes` are named individuals, but they are primarily defined by their species role, not as person-equivalents. Keeping them in CREA makes the boundary clear and consistent.

The exception is when a non-human entity is written and treated *as a person* — with dialogue, independent moral decisions, a social role, and consistent individual personality across scenes. In that case, use CHAR (e.g., `Dobby`, `Griphook`, `Firenze`). See the CHAR section for this boundary.

**Why not label generic pets like cats and owls?**  
A generic cat or owl is just an animal — it is not a *named entity* in the NER sense. A named individual animal (`Crookshanks`, `Hedwig`) is an entity worth labelling because the name makes it uniquely identifiable. An unnamed cat has no identity beyond being an animal, so it adds no useful information for NER.

✅ **Include:**
- Named individual creatures: `Buckbeak`, `Fawkes`, `Nagini`, `Fluffy`, `Aragog`, `Norbert`
- Named species (when functioning as a class noun with an established name): `Dementor`, `hippogriff`, `basilisk`, `house-elf`, `Thestral`, `werewolf`, `centaur`
- Non-human sentient beings referred to by species: `a goblin`, `a vampire`, `a giant`, `a mermaid`, `a Veela`
- Named pets: `Crookshanks`, `Hedwig`, `Trevor`, `Scabbers`

❌ **Exclude:**
- Generic real-world animals: `a cat`, `an owl`, `a rat` (unless named)
- Named individuals with person-level agency → use CHAR: `Dobby`, `Griphook`, `Firenze`
- Generic: `the creature`, `a beast`, `the animal`

**CHAR vs CREA boundary rule:**  
Use **CHAR** if the entity:
- Has a proper name AND
- Is written with consistent individual personality across scenes AND
- Has significant narrative agency (makes decisions, speaks, has relationships)

Use **CREA** if the entity:
- Is primarily defined by its species role OR
- Is named but functions mainly as an animal or creature (not a person-equivalent)

**Tricky cases:**

| Text | Decision | Reason |
|------|----------|--------|
| `Dobby` | CHAR | Named, consistent personality, moral agency, treated as person |
| `Griphook` | CHAR | Named goblin with individual role and agency |
| `Firenze` | CHAR | Named centaur who joins Hogwarts staff, individual role |
| `Buckbeak` | CREA | Named, but primarily defined as a hippogriff |
| `Fawkes` | CREA | Named phoenix, but primarily creature role |
| `Nagini` | CREA | Named snake/Maledictus, primarily creature role |
| `a Dementor` | CREA | Named species |
| `the house-elf` | CREA | Generic species reference |
| `Remus Lupin` | CHAR | Human who is a werewolf — CHAR wins |
| `a werewolf` | CREA | Species reference |
| `a Patronus` | CREA | Magical creature produced by a spell |
| `Crookshanks` | CREA | Named cat — named pet, but functions as an animal |
| `Hedwig` | CREA | Named owl — same reasoning |
| `goblins` | CREA | Species reference |

---

### ARTIFACT (`ARTI`)

Any **named magical object, item, potion, book, or artefact**. This includes potions — they are physical objects that are brewed, stored, and consumed, and belong in this category.

**Why are potions ARTIFACT?**  
Potions are not incantations or magical effects (which are SPELL) — they are physical substances that exist as objects in the world. A bottle of `Polyjuice Potion` is as much an artifact as `the Invisibility Cloak`. Treating them as ARTIFACT keeps the SPELL category focused on incantations and named magical effects performed through wands or intent.

✅ **Include:**
- Named magical objects: `the Elder Wand`, `the Sorting Hat`, `the Marauder's Map`
- Named Horcruxes: `Tom Riddle's Diary`, `Hufflepuff's Cup`, `Slytherin's Locket`
- Named potions: `Polyjuice Potion`, `Felix Felicis`, `Veritaserum`, `Amortentia`, `Wolfsbane Potion`
- Named books as objects: `Hogwarts: A History`, `The Monster Book of Monsters`
- Named vehicles: `the Hogwarts Express`, `the Knight Bus`, `the Flying Ford Anglia`
- Named weapons: `the Sword of Gryffindor`
- Deathly Hallows: `the Invisibility Cloak`, `the Resurrection Stone`, `the Elder Wand`
- Named magical devices: `a Time-Turner`, `the Sneakoscope`, `the Deluminator`

❌ **Exclude:**
- Generic objects: `a wand`, `a broomstick`, `a cauldron`, `a potion`
- Unnamed items: `his cloak`, `her bag`, `the old book`
- Spell names (even if the spell produces an artifact): `Accio` is SPELL, not ARTI

**Tricky cases:**

| Text | Decision | Reason |
|------|----------|--------|
| `Polyjuice Potion` | ARTI | Named potion = artifact |
| `a potion` | ❌ | Generic |
| `the Sorting Hat` | ARTI | Named magical object |
| `the Philosopher's Stone` | ARTI | Named artifact |
| `a Time-Turner` | ARTI | Named object (even without specific name) |
| `the Hogwarts Express` | ARTI | Named vehicle |
| `the Daily Prophet` (physical copy) | ARTI | Physical newspaper object |
| `the Daily Prophet` (institution) | ORG | |
| `the Invisibility Cloak` | ARTI | Named Deathly Hallow |
| `an invisibility cloak` | ❌ | Generic object |

---

## 4. Span Boundaries

Annotate the **minimal identifying span** that uniquely identifies the entity. Include titles and qualifiers only when they are grammatically part of the established name or when title+name together is the standard form of reference.

### Titles and names

| Text | Annotate | Label |
|------|----------|-------|
| `Professor Dumbledore` | `Professor Dumbledore` | CHAR |
| `Lord Voldemort` | `Lord Voldemort` | CHAR |
| `Minister Fudge` | `Minister Fudge` | CHAR |
| `Madam Pomfrey` | `Madam Pomfrey` | CHAR |
| `the professor` | ❌ | |
| `Hogwarts School of Witchcraft and Wizardry` | `Hogwarts School of Witchcraft and Wizardry` | ORG |
| `the school` | ❌ | |

### Possessives

Annotate the **name only**, not the `'s` — unless the possessive is part of the established group/object name:

| Text | Annotate | Label |
|------|----------|-------|
| `Harry's wand` | `Harry` | CHAR |
| `Dumbledore's Army` | `Dumbledore's Army` | ORG (the possessive is part of the name) |
| `Hufflepuff's Cup` | `Hufflepuff's Cup` | ARTI (part of the artifact's name) |
| `Slytherin's Locket` | `Slytherin's Locket` | ARTI |
| `Voldemort's snake` | `Voldemort` | CHAR |

### Multi-word spans

Always annotate the full identifying span as a single entity:

| Text | Annotate | Label |
|------|----------|-------|
| `the Order of the Phoenix` | `Order of the Phoenix` | ORG |
| `the Chamber of Secrets` | `Chamber of Secrets` | LOC |
| `the Killing Curse` | `Killing Curse` | SPELL |
| `Wingardium Leviosa` | `Wingardium Leviosa` | SPELL |
| `the Boy Who Lived` | `the Boy Who Lived` | CHAR |

---

## 5. IOB2 Format

Each token gets exactly one tag:
| Token   | Tag          |
|---------|--------------|
| Harry        | B-CHAR  |
| Potter       | I-CHAR  |
| cast         | O       |
| Expelliarmus | B-SPELL |
| at           | O       |
| Professor    | B-CHAR  |
| Snape        | I-CHAR  |
| .            | O       |

- `B-TYPE` — **B**eginning of an entity span
- `I-TYPE` — **I**nside (continuation of) the same entity span
- `O` — not part of any entity
- A new `B-` **always** starts a new entity, even if the same type follows immediately
- Every token in a span after the first gets `I-`, including function words that are part of the name

---

## 6. Handling Silver Pre-Annotations

Doccano will show **silver pre-annotations** already filled in. These come from dictionary matching and BERT predictions. They are a starting point — **not ground truth**. Your job is to:

- ✅ **Confirm** correct labels
- ✏️ **Fix** wrong labels (wrong type, wrong span boundary)
- ➕ **Add** missing entities
- ❌ **Remove** false positives

### Known silver failure modes

| What you see | What to do |
|-------------|-----------|
| Common word tagged as CHAR (e.g., `house`, `name`) | Remove — false dictionary match |
| Character name missing entirely | Add it |
| `Hogwarts` always tagged as ORG | Check context — change to LOC if spatial |
| SPELL labels missing | Actively look — BERT misses these most often |
| Potion tagged as SPELL | Change to ARTI |
| Named creature tagged as CHAR | Check CHAR vs CREA boundary rule |
| Long entity span broken into pieces | Fix span boundaries |
| `the` included in the entity span | Remove the `the` from the span |

---

## 7. Annotation Workflow

### Overview of files

Each annotator has two files in Doccano:
- **`overlap_set.jsonl`** — ~188 sentences annotated by **all 4 annotators** for IAA
- **`{your_name}_unique.jsonl`** — sentences only you annotate

> ⚠️ The unique files are **never shared or seen by other annotators**. They are merged into the final dataset only after adjudication of the overlap set is complete.

### Recommended order

**Start with the overlap set.** This ensures everyone is calibrating on the same sentences before they diverge into unique work.

---

### Phase 1 — Calibration (Overlap set, first 10 sentences)

1. Open `overlap_set.jsonl` in Doccano
2. Annotate the **first 5 sentences** independently — do not discuss yet
3. **Stop.** Share your annotations for those 5 sentences with the group (screenshot or export)
4. Discuss every disagreement — reach a consensus decision
5. Update your annotations if needed
6. Annotate the **next 5 sentences** independently
7. Repeat the share + discuss step
8. Document any new edge cases in these guidelines (add a comment in the GitHub file)

---

### Phase 2 — Overlap annotation (Overlap set, remaining sentences)

After the first 10 calibration sentences:

| Checkpoint | When | Action |
|-----------|------|--------|
| Every 25 sentences | During overlap annotation | Quick self-check: are you applying rules consistently? Flag uncertain cases with a Doccano comment |
| After 50 sentences | Mid-overlap | Share flagged cases with the group in the group chat — discuss and resolve |
| After completing overlap set | End of Phase 2 | **Zita runs `run_agreement.py`** on all overlap annotations — reports κ per label |

**If κ ≥ 0.7 for all labels:** proceed to Phase 3  
**If κ < 0.7 for any label:** hold an adjudication session (see Section 9), update guidelines, and **re-annotate the affected overlap sentences** before proceeding

---

### Phase 3 — Unique annotation

After the overlap set is complete and IAA is satisfactory:

1. Open your `{name}_unique.jsonl` file
2. Annotate independently

| Checkpoint | When | Action |
|-----------|------|--------|
| After 25 unique sentences | Early unique | Self-check — are edge cases consistent with what was decided in Phase 2? |
| After 50 unique sentences | Mid unique | Bring any new edge cases to the group chat |
| After completing unique file | End of Phase 3 | Signal to the group that you are done |

---

### Phase 4 — Final merge and split

After all annotators complete their unique files:

1. **Hanna** leads adjudication on any remaining overlap disagreements (see Section 9)
2. **Peter** runs the 80/10/10 stratified train/dev/test split on the merged gold set
3. **Zita** verifies split balance with per-class entity count stats
4. Final export to `data/annotated/`

---

### When you are unsure

1. Check these guidelines first — use the quick reference table at the bottom
2. Check your already-annotated sentences — be consistent with what you did before
3. If still unsure: add a **Doccano comment** on the sentence with your question, e.g.:  
   `"UNSURE: is 'the Chosen One' here a CHAR nickname or just a description?"`
4. Bring it to the group at the next checkpoint — **do not skip it or guess without flagging it**

---

## 8. Per-Annotator Focus Areas

During annotation, apply all label types as best you can. Your focus area means:
- You are the **domain expert** for those types
- When reviewing disagreements in adjudication, your judgment carries extra weight for those types
- You should actively look for missed entities in your focus area

| Annotator | Primary focus | Key ambiguities to watch |
|-----------|--------------|--------------------------|
| **Hanna** | CHAR, ARTI | CHAR vs ARTI (e.g., the Sorting Hat — is it just an object or does it have enough character?); nicknames and titles as CHAR; possessives |
| **Zita** | LOC, ORG | LOC vs ORG (the Hogwarts rule); unnamed locations; CHAR vs ORG (house names) |
| **Anis** | SPELL, CREA, CHAR | SPELL vs ARTI (potions); CREA vs CHAR boundary (named creatures with agency); missing spell labels |
| **Peter** | General consistency, CHAR vs ORG | Overall IOB2 format correctness; span boundary errors; CHAR vs ORG (group names vs individuals) |

> When you encounter an ambiguity **outside** your focus area, still annotate your best guess and add a Doccano comment. The responsible annotator will review during adjudication.

---

## 9. Adjudication

Adjudication applies **only to the overlap set**. Unique sentences are never seen by other annotators and do not go through adjudication — they are merged directly into the final dataset after Phase 4.

### When adjudication happens

- After Phase 2 if κ < 0.7 for any label
- After Phase 3 for any remaining unresolved overlap disagreements

### Process

1. **Zita** exports overlap disagreements from `run_agreement.py` — a list of sentences where annotators disagree
2. **Hanna** calls an adjudication session (video call or async discussion)
3. For each disagreement:
   - Each annotator explains their reasoning
   - **Majority vote (3/4) wins**
   - If 2-2 split: **Hanna makes the final call** and documents the reasoning in the guidelines
4. All annotators update their overlap annotations to match the adjudicated decision
5. Any new rule created during adjudication is added to these guidelines immediately
6. **Zita re-runs `run_agreement.py`** to confirm κ ≥ 0.7 after updates

### What gets documented

Every adjudicated decision that reveals a gap in the guidelines should be added to the relevant section above, with an example. The goal is that future ambiguous cases of the same type can be resolved by reading the guidelines alone.

---

## 10. Quick Reference

### Entity type summary

| Type | Label | Examples | Not |
|------|-------|---------|-----|
| Character | CHAR | `Harry Potter`, `Professor Dumbledore`, `the Dark Lord`, `Dobby` | `the wizard`, `he`, `the professor` |
| Location | LOC | `Hogwarts` (place), `Diagon Alley`, `London`, `the Forbidden Forest` | `the school`, `a room`, `upstairs` |
| Organization | ORG | `Hogwarts School of Witchcraft and Wizardry`, `Death Eaters`, `Ministry of Magic` | `a group`, `the teachers` |
| Spell | SPELL | `Expelliarmus`, `the Patronus Charm`, `the Unforgivable Curses` | `a spell`, potions, `magic` |
| Creature | CREA | `Buckbeak`, `Dementor`, `house-elf`, `hippogriff`, `Fawkes` | generic animals, creatures with person-level agency |
| Artifact | ARTI | `the Elder Wand`, `Polyjuice Potion`, `the Marauder's Map` | `a wand`, `a cauldron`, generic objects |

### Common decisions

| Text | Label | Note |
|------|-------|------|
| `Professor Dumbledore` | CHAR | Full span — title + name together |
| `the Chosen One` | CHAR | Nickname |
| `Hogwarts` (spatial) | LOC | |
| `Hogwarts School of Witchcraft and Wizardry` | ORG | Institutional name |
| `Death Eaters` | ORG | Named group |
| `a Death Eater` | ❌ | Generic |
| `Expelliarmus` | SPELL | |
| `the Patronus Charm` | SPELL | |
| `a Patronus` | CREA | The creature, not the spell |
| `Polyjuice Potion` | ARTI | Potion = artifact |
| `Buckbeak` | CREA | Named creature, not person-level agency |
| `Dobby` | CHAR | Named, person-level agency |
| `the Elder Wand` | ARTI | Article excluded from span: `Elder Wand` |
| `Death Eaters` vs `the Death Eaters` | ORG | Annotate `Death Eaters` — exclude `the` |
| `Dumbledore's Army` | ORG | Possessive is part of the name |
| `Harry's wand` | `Harry` = CHAR | Possessive — annotate name only |
| `the Battle of Hogwarts` | ❌ event | `Hogwarts` standalone = LOC |
| `S.P.E.W.` | ORG | Named society |
| `the Daily Prophet` (outlet) | ORG | |
| `a copy of the Daily Prophet` | ARTI | Physical object |
| `Ministry of Magic` | ORG | Exclude leading `the` |
| `Ministry corridors` | LOC | Physical space |
| `Twitter` | ORG | Real-world org |
| `London` | LOC | Real-world location |