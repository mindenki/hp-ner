# Doccano Annotation Guide — HP-NER

_Historical: the team also briefly hosted Doccano on an Azure VM during phase 2; those artefacts live under [legacy/](../legacy/)._

---

## Setup

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

**Manual (browser):**

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
