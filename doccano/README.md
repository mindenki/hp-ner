# Doccano Annotation Guide — HP-NER

This guide covers two workflows:

- **Shared server (recommended):** log in to the team's Azure-hosted Doccano instance
- **Local setup:** run Doccano on your own machine (fallback only)

---

## Option A — Shared Server (Azure)

No installation needed. Everything is already set up.

### 1. Open the annotation tool

Go to: **https://hp-ner.swedencentral.cloudapp.azure.com**

### 2. Log in

| Annotator | Username | Password       |
| --------- | -------- | -------------- |
| Peter     | `peter`  | `annotate2024` |
| Hanna     | `hanna`  | `annotate2024` |
| Zita      | `zita`   | `annotate2024` |
| Anis      | `anis`   | `annotate2024` |

Your project will be pre-loaded with your sentences. Click into it and start annotating.

> **Note:** The admin account (`admin`) manages projects and imports.
> Annotators should log in with their own accounts only.

---

## Option B — Local Setup (fallback)

Use this only if the shared server is unavailable.

### Prerequisites

Install **Docker Desktop** (one-time, ~5 min):

| OS      | Link                                                     |
| ------- | -------------------------------------------------------- |
| macOS   | https://docs.docker.com/desktop/install/mac-install/     |
| Windows | https://docs.docker.com/desktop/install/windows-install/ |
| Linux   | https://docs.docker.com/desktop/install/linux-install/   |

After installation, start Docker Desktop and wait for the whale icon in the
menu bar / system tray before continuing.

### One-time Setup

```bash
# 1. Copy the environment template
cp doccano/.env.example doccano/.env
```

Windows PowerShell:

```powershell
Copy-Item doccano/.env.example doccano/.env
```

Windows Command Prompt:

```bat
copy doccano\.env.example doccano\.env
```

```bash
# 2. Start Doccano
cd doccano
docker compose up doccano
```

Open http://localhost:8000. Log in with:

- **Username:** `admin`
- **Password:** `hpner2024`

### Create the Annotation Project

**Option 1 — Script (recommended):**

```bash
# From the project root:
uv run python scripts/annotation/setup_doccano_project.py --annotator peter

# Import only overlap set:
uv run python scripts/annotation/setup_doccano_project.py --annotator peter --import-scope overlap

# Import only personal set:
uv run python scripts/annotation/setup_doccano_project.py --annotator peter --import-scope personal

# Skip import (create project + labels only):
uv run python scripts/annotation/setup_doccano_project.py --skip-import
```

**Option 2 — Manual (browser):**

1. Click **Create** → **Sequence Labeling**
2. Name: `HP-NER Gold - <yourname> - <date>`
3. In the left sidebar → **Labels** → **Create label** — add each row:

| Label          | Key | Color     |
| -------------- | --- | --------- |
| `Character`    | `c` | `#4A90D9` |
| `Location`     | `l` | `#7CB342` |
| `Organization` | `o` | `#F4A335` |
| `Creature`     | `r` | `#9C27B0` |
| `Spell`        | `s` | `#E53935` |
| `Artifact`     | `a` | `#00897B` |

### Import Your Sentences

> Skip this if you used the script above — sentences are already imported.

| File                       | Description                               |
| -------------------------- | ----------------------------------------- |
| `overlap.jsonl`            | Sentences annotated by everyone (for IAA) |
| `<your_name>_unique.jsonl` | 350 sentences assigned only to you        |

1. In your project → **Dataset** → **Actions** → **Import Dataset**
2. Format: **JSONL**
3. Import `overlap.jsonl`, then `<your_name>_unique.jsonl`

### Stopping and Resuming

Annotations are stored in a Docker volume and persist across restarts.

```bash
# Stop
docker compose down

# Resume
docker compose up doccano
```

---

## Annotating

Applies to both workflows.

1. Open your project → click **Start Annotation**
2. **Highlight** a text span with the mouse
3. Press the shortcut key (e.g. `c` for Character) or select from the popup
4. Click **Next** or press the right-arrow key to advance

To **remove** a label: click the ✕ on the span badge.

---

## Annotation Guidelines

**Character** — any named person or ghost; e.g. "Harry Potter", "Nearly Headless Nick".
Not pronouns, not "the boy".

**Location** — named places; e.g. "Hogwarts", "Diagon Alley", "the Forbidden Forest".

**Organization** — named groups or institutions; e.g. "Order of the Phoenix",
"Death Eaters", "Ministry of Magic".

**Creature** — non-human magical beings; e.g. "Buckbeak", "Aragog", "Dobby".
Note: house-elves and goblins are Creatures, not Characters.

**Spell** — incantation words only; e.g. "Expelliarmus", "Lumos".
NOT descriptions like "the disarming spell".

**Artifact** — named magical objects; e.g. "Elder Wand", "Marauder's Map",
"Philosopher's Stone". NOT generic items like "his wand".

**Span boundaries** — include the full proper name. "Harry Potter" → full span,
not just "Harry".

When in doubt: if you would capitalise it in a Harry Potter encyclopedia entry,
it's an entity. If unsure of the type, pick the closest one and move on.

---

## Exporting Your Annotations

### Shared server

Server handles exports via the deploy scripts. Nothing to do on your end —
just annotate and the daily sync pulls your progress automatically.

### Local setup

**Option 1 — Script:**

```bash
# Export all projects
uv run python scripts/annotation/export_annotations.py

# Export only overlap
uv run python scripts/annotation/export_annotations.py --export-scope overlap
```

Files are written to `data/annotated/` as:

- `<project_name>_overlap.jsonl`
- `<project_name>_personal.jsonl`

**Option 2 — Manual:**

1. **Dataset** → **Actions** → **Export Dataset** → format: **JSONL**
2. Rename to `<your_name>_export.jsonl` and send to Peter

---

## Troubleshooting

**Container won't start** — make sure Docker Desktop is running (whale icon visible).

**Port 8000 already in use** — change `"8000:8000"` to `"8001:8000"` in
`docker-compose.yml`, then open http://localhost:8001.

**Forgot password** — edit `doccano/.env`, then:

```bash
docker compose down
docker volume rm doccano_doccano-db   # ⚠ deletes all annotations
docker compose up doccano
```

**Pre-annotations not visible** — make sure you imported the JSONL file correctly.
Re-import if needed (duplicate sentences are harmless; delete extras via the UI).

**Can't reach the shared server** — check your internet connection, then contact
Peter. As a fallback, switch to Option B (local setup) above.
