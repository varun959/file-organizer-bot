# File Organizer — User Manual

File Organizer sorts loose files in a directory into categorized subfolders. It is safe to use: every real run writes an undo manifest so you can always reverse it.

---

## Requirements

- Python 3.9 or later
- No third-party dependencies

---

## Basic Usage

```
python3 organizer.py <directory> [options]
```

---

## Options

| Flag | Description |
|------|-------------|
| `--dry-run` | Preview what would happen without moving anything |
| `--undo` | Restore files to where they were before the last run |
| `--history` | Show all runs on this machine, or pass a directory to show that directory's history |
| `--report FILE` | Save a JSON summary of the run to FILE |
| `--verbose` / `-v` | Show detailed per-file logging |
| `--help` / `-h` | Show usage information |

---

## How It Works

Running the organizer on a directory moves every file in the root of that directory into a named subfolder based on its extension:

```
my-folder/
  photo.jpg       →   my-folder/images/photo.jpg
  budget.xlsx     →   my-folder/documents/budget.xlsx
  script.py       →   my-folder/code/script.py
  notes.txt       →   my-folder/text/notes.txt
  archive.zip     →   my-folder/archives/archive.zip
```

Only files directly in the root are moved. Existing subfolders and their contents are left untouched.

**Name conflicts** are handled automatically. If a file with the same name already exists in the destination, a counter is appended:

```
photo.jpg → images/photo.jpg        (already exists)
photo.jpg → images/photo (1).jpg    (new file saved here)
```

**Dotfiles** (files whose names begin with `.`) are never moved.

---

## File Categories

| Category | Extensions |
|----------|-----------|
| `images` | .jpg .jpeg .png .gif .bmp .svg .webp .tiff .ico .heic |
| `videos` | .mp4 .mov .avi .mkv .wmv .flv .webm .m4v |
| `audio` | .mp3 .wav .flac .aac .ogg .wma .m4a |
| `documents` | .pdf .doc .docx .xls .xlsx .ppt .pptx .odt .pages .numbers |
| `text` | .txt .md .rst .csv .log .rtf |
| `code` | .py .js .ts .html .css .java .c .cpp .h .go .rs .rb .php .sh .bash .zsh .json .yaml .yml .toml .xml .sql |
| `archives` | .zip .tar .gz .bz2 .xz .7z .rar .dmg .iso |
| `executables` | .exe .app .msi .deb .rpm .pkg |
| `fonts` | .ttf .otf .woff .woff2 .eot |
| `misc` | anything else |

---

## Examples

**Preview before committing:**
```
python3 organizer.py ~/Downloads --dry-run
```

**Organize for real:**
```
python3 organizer.py ~/Downloads
```

**Organize with verbose output:**
```
python3 organizer.py ~/Downloads --verbose
```

**Undo the last run:**
```
python3 organizer.py ~/Downloads --undo
```

**Preview what undo would do:**
```
python3 organizer.py ~/Downloads --undo --dry-run
```

**Save a JSON report of the run:**
```
python3 organizer.py ~/Downloads --report report.json
```

**View history of all runs on this machine:**
```
python3 organizer.py --history
```

**View history for a specific directory:**
```
python3 organizer.py ~/Downloads --history
```

Both display a formatted table showing each run's timestamp, type, file count, and directory.

---

## Undo

Every real run (not dry-run) writes an undo manifest to the target directory at `.organizer_undo.json`. This records the exact source and destination of every file that was moved.

Running with `--undo` reads this manifest and reverses every move. After a successful undo:

- Files are restored to their original locations in the directory root
- Any category subfolders that are now empty are removed
- The undo manifest is deleted

**Note:** Undo is a one-shot operation. It reverses the most recent run only. There is no multi-level undo.

If a file has been moved or deleted since the last organize run, it is skipped with a warning and the rest of the files are still restored.

---

## Logs

The organizer keeps two logs, one for you and one for your administrator or support contact.

### Per-directory log

Location: `<target-directory>/.organizer_history.json`

Records every organize and undo operation performed on that specific directory. Useful for reviewing what has been done to a folder over time. Travels with the directory if you move or share it.

### Central log

Location: `~/.local/share/organizer/history.json`

Records every organize and undo operation across all directories on this machine. Includes the target directory path in each entry. Useful for a full audit trail.

Both logs are append-only JSON arrays. Dry-run operations are not logged.

**Example central log entry:**
```json
{
  "type": "organize",
  "run_at": "2026-03-01T16:13:53",
  "directory": "/Users/alice/Downloads",
  "files_moved": 24,
  "size_bytes": 183452,
  "categories": {
    "images": 10,
    "documents": 8,
    "code": 4,
    "misc": 2
  }
}
```

---

## Files Written to the Target Directory

| File | Purpose |
|------|---------|
| `.organizer_undo.json` | Undo manifest for the last run (overwritten each run, deleted after undo) |
| `.organizer_history.json` | Cumulative per-directory history log |

Both are dotfiles and will never be moved by the organizer itself.
