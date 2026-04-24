# Doccano Annotation Guide - HP-NER

This guide walks each annotator through setting up their local Doccano instance,
importing sentences, annotating, and exporting results back to Peter.

---

## Prerequisites

Install **Docker Desktop** (one-time, ~5 min):

| OS      | Link                                                     |
| ------- | -------------------------------------------------------- |
| macOS   | https://docs.docker.com/desktop/install/mac-install/     |
| Windows | https://docs.docker.com/desktop/install/windows-install/ |
| Linux   | https://docs.docker.com/desktop/install/linux-install/   |

After installation, start Docker Desktop and wait for the whale icon to appear
in the menu bar / system tray before continuing.

---

## One-time Setup

```bash
# 1. Copy the environment template (only needed once, or create your own)
cp doccano/.env.example doccano/.env

# 2. Start Doccano (runs in the background)
cd doccano
docker compose up -d
```

If `cp` is not available on your machine, use one of these instead:

```powershell
# Windows PowerShell
Copy-Item doccano/.env.example doccano/.env
```

```bat
:: Windows Command Prompt (cmd.exe)
copy doccano\.env.example doccano\.env
```

Open http://localhost:8000 in your browser. Log in with:

- **Username:** `admin`
- **Password:** `hpner2024`

> You can change the password in `doccano/.env` before running `docker compose up -d`.
> If you change it after the first run, recreate the container:
> `docker compose down && docker compose up -d`

---

## Create the Annotation Project

You have two options — the script is faster and less error-prone.

### Option A: Script (recommended)

Make sure Doccano is running, then from the **project root**:

```bash
# Run this once to create the project and import everyone's sentences
uv run python scripts/annotation/setup_doccano_project.py --annotator peter
```

This creates a project with the default name pattern:

`HP-NER Gold - {annotator} - {run_id}`

where `run_id` is a timestamp (for example `20260424_153200`), adds all 6 labels
with the correct colours and keyboard shortcuts, and imports JSONL batch files.

To use a custom password or URL:

```bash
uv run python scripts/annotation/setup_doccano_project.py --password mypassword --base-url http://localhost:8000
```

To set an explicit run identifier (useful for repeated imports):

```bash
uv run python scripts/annotation/setup_doccano_project.py --annotator peter --run-id overlap_fix_01
```

To import only one split:

```bash
# overlap only
uv run python scripts/annotation/setup_doccano_project.py --annotator peter --import-scope overlap

# personal only
uv run python scripts/annotation/setup_doccano_project.py --annotator peter --import-scope personal
```

To create the project and labels without importing files yet (e.g. if you want
to distribute files separately):

```bash
uv run python scripts/annotation/setup_doccano_project.py --skip-import
```

### Option B: Manual (browser)

Do this once in your browser after logging in:

1. Click **Create** -> choose **Sequence Labeling**
2. Name: use a unique name, e.g. `HP-NER Gold - peter - 20260424_153200`
3. Leave all other options at their defaults -> **Create**

Then in the left sidebar, click **Labels** -> **Create label** and add each row:

| Label          | Key | Color     |
| -------------- | --- | --------- |
| `Character`    | `c` | `#4A90D9` |
| `Location`     | `l` | `#7CB342` |
| `Organization` | `o` | `#F4A335` |
| `Creature`     | `r` | `#9C27B0` |
| `Spell`        | `s` | `#E53935` |
| `Artifact`     | `a` | `#00897B` |

Set the **Shortcut key** field for each label - this lets you annotate without
touching the mouse.

---

## Import Your Sentences

> **If you used the script above, your sentences are already imported — skip this section.**


| File                       | Description                                   |
| -------------------------- | --------------------------------------------- |
| `overlap.jsonl`            | Sentences annotated by everyone (for IAA)     |
| `<your_name>_unique.jsonl` | 350 sentences assigned only to you            |

Import them in this order:

1. In your project, go to **Dataset** -> **Actions** -> **Import Dataset**
2. Format: **JSONL**
3. Select `overlap.jsonl` -> **Import**
4. Repeat for `<your_name>_unique.jsonl`

The silver labels will load as pre-annotations - you correct them rather than
starting from scratch.

---

## Annotating

1. Open your project -> click into the sentence list
2. **Highlight** a text span with the mouse
3. Press the shortcut key (e.g. `c` for Character) - or select from the popup
4. Click **Next** or press the right-arrow key to advance

To **remove** a label: click the ✕ on the span badge.

### Annotation Guidelines

**Character** - any named person or ghost; e.g. "Harry Potter", "Nearly Headless Nick".
Not pronouns, not "the boy".

**Location** - named places; e.g. "Hogwarts", "Diagon Alley", "the Forbidden Forest".

**Organization** - named groups or institutions; e.g. "Order of the Phoenix",
"Death Eaters", "Ministry of Magic".

**Creature** - non-human magical beings; e.g. "Buckbeak", "Aragog", "Dobby".
Note: house-elves and goblins are Creatures, not Characters.

**Spell** - incantation words only; e.g. "Expelliarmus", "Lumos".
NOT descriptions like "the disarming spell".

**Artifact** - named magical objects; e.g. "Elder Wand", "Marauder's Map",
"Philosopher's Stone". NOT generic items like "his wand".

**Span boundaries** - include the full proper name. "Harry Potter" -> full span,
not just "Harry".

When in doubt: if you would capitalise it in a Harry Potter encyclopedia entry,
it's an entity. If you're unsure of the type, pick the closest one and move on.

---

## Stopping and Resuming

Annotations are stored in a Docker volume and persist across restarts.

```bash
# Stop Doccano (your annotations are safe)
docker compose down

# Resume later
docker compose up -d
```

---

## Exporting Your Annotations

When you've finished all your sentences:

### Option A: Script (recommended)

```bash
# Export all projects and split to overlap/personal files
uv run python scripts/annotation/export_annotations.py

# Export only overlap split
uv run python scripts/annotation/export_annotations.py --export-scope overlap

# Export only selected project IDs
uv run python scripts/annotation/export_annotations.py --project-ids 12 13
```

This writes files to `data/annotated/` as:

- `<project_name>_overlap.jsonl`
- `<project_name>_personal.jsonl`

### Option B: Manual (browser)

1. In your project, go to **Dataset** -> **Actions** -> **Export Dataset**
2. Format: **JSONL**
3. Save the downloaded file
4. Rename it to `<your_name>_export.jsonl` and either upload it to GitHub or share it with the team

---

## Troubleshooting

**Container won't start** - make sure Docker Desktop is running (whale icon visible).

**Port 8000 already in use** - change `"8000:8000"` to `"8001:8000"` in
`docker-compose.yml`, then open http://localhost:8001.

**Forgot password** - edit `doccano/.env`, then:

```bash
docker compose down
docker volume rm doccano_doccano-db   # deletes all annotations - only do this if you haven't started yet
docker compose up -d
```

**Pre-annotations not visible** - make sure you imported the JSONL file correctly.
Re-import if needed (duplicate sentences are harmless; just delete extras via the UI).
