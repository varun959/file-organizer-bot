# File Organizer

A command-line tool that sorts loose files into categorized subfolders. Every run is fully reversible, and a complete audit trail is kept for both users and maintainers.

---

## Features

- **Automatic categorization** — sorts files by extension into named subfolders (`images/`, `code/`, `documents/`, and more)
- **Safe by default** — `--dry-run` previews exactly what would happen before any files are moved
- **Full undo** — every run writes a manifest so you can restore all files to their original locations
- **Collision handling** — name conflicts are resolved automatically with a counter suffix, no files are ever overwritten
- **Dotfile protection** — hidden files (`.anything`) are never moved
- **Dual history logs** — a per-directory log for users and a machine-wide central log for maintainers
- **JSON reports** — optionally export a summary of any run to a JSON file

---

## Requirements

- Python 3.9 or later
- No third-party dependencies

---

## Installation

Clone the repository and run directly — no installation needed:

```bash
git clone https://github.com/yourname/file-organizer-bot.git
cd file-organizer-bot
python3 organizer.py --help
```

---

## Usage

```
python3 organizer.py <directory> [options]
```

### Options

| Flag | Description |
|------|-------------|
| `--dry-run` | Preview changes without moving any files |
| `--undo` | Restore files to their original locations |
| `--history` | Show all runs on this machine |
| `--report FILE` | Save a JSON summary report to FILE |
| `--verbose` / `-v` | Show per-file logging |

### Examples

```bash
# Preview what would be moved
python3 organizer.py ~/Downloads --dry-run

# Organize for real
python3 organizer.py ~/Downloads

# Undo the last run
python3 organizer.py ~/Downloads --undo

# Preview an undo before committing
python3 organizer.py ~/Downloads --undo --dry-run

# View history for a specific directory
python3 organizer.py ~/Downloads --history

# View history of all runs on this machine
python3 organizer.py --history

# Save a JSON report
python3 organizer.py ~/Downloads --report report.json
```

---

## How It Works

The organizer scans the root of the target directory for files and moves each one into a subfolder named after its category:

```
Downloads/
  photo.jpg        →  Downloads/images/photo.jpg
  budget.xlsx      →  Downloads/documents/budget.xlsx
  script.py        →  Downloads/code/script.py
  notes.txt        →  Downloads/text/notes.txt
  archive.zip      →  Downloads/archives/archive.zip
  unknown.xyz      →  Downloads/misc/unknown.xyz
```

Only files directly in the root are touched — existing subfolders and their contents are left alone.

### File Categories

| Category | Common Extensions |
|----------|------------------|
| `images` | .jpg .png .gif .svg .webp .heic … |
| `videos` | .mp4 .mov .avi .mkv … |
| `audio` | .mp3 .wav .flac .aac … |
| `documents` | .pdf .doc .docx .xls .xlsx .ppt … |
| `text` | .txt .md .csv .log .rst … |
| `code` | .py .js .ts .html .css .go .rs .json .yaml … |
| `archives` | .zip .tar .gz .7z .dmg … |
| `executables` | .exe .app .msi .pkg … |
| `fonts` | .ttf .otf .woff .woff2 … |
| `misc` | everything else |

### Undo

Every real run writes an undo manifest (`.organizer_undo.json`) to the target directory recording every move made. `--undo` reads this manifest and reverses each move exactly. After a successful undo, empty category folders are removed and the manifest is deleted.

### History Logs

Two logs are maintained automatically after every real run:

- **Per-directory** — `.organizer_history.json` in the target directory. Records all organize and undo operations on that folder. Travels with the directory.
- **Central** — `~/.local/share/organizer/history.json`. Records all operations across every directory on the machine, including the directory path. Useful for support and auditing.

Neither log is written during dry-run operations.

---

## Running Tests

```bash
python3 -m pytest test_organizer.py -v
```

73 tests covering categorization, collision handling, dry-run, undo, history logging, and more.

---

## Project Structure

```
file-organizer-bot/
├── organizer.py          # Main CLI tool
├── test_organizer.py     # Test suite
├── USER_MANUAL.md        # Full user manual
└── README.md             # This file
```
