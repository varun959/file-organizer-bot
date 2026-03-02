"""
File Organizer - Sorts files in a directory into categorized subfolders.

Usage:
    python organizer.py <target_directory> [--dry-run] [--report report.json]
"""

import argparse
import json
import logging
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

from platformdirs import user_data_dir

# --- Configuration ---

VERSION = "1.0.0"

UNDO_FILE = ".organizer_undo.json"
HISTORY_FILE = ".organizer_history.json"
CENTRAL_LOG = Path(user_data_dir("organizer")) / "history.json"

FILE_CATEGORIES = {
    "images":     {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".svg", ".webp", ".tiff", ".ico", ".heic"},
    "videos":     {".mp4", ".mov", ".avi", ".mkv", ".wmv", ".flv", ".webm", ".m4v"},
    "audio":      {".mp3", ".wav", ".flac", ".aac", ".ogg", ".wma", ".m4a"},
    "documents":  {".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".odt", ".pages", ".numbers"},
    "text":       {".txt", ".md", ".rst", ".csv", ".log", ".rtf"},
    "code":       {".py", ".js", ".ts", ".html", ".css", ".java", ".c", ".cpp", ".h",
                   ".go", ".rs", ".rb", ".php", ".sh", ".bash", ".zsh", ".json",
                   ".yaml", ".yml", ".toml", ".xml", ".sql"},
    "archives":   {".zip", ".tar", ".gz", ".bz2", ".xz", ".7z", ".rar", ".dmg", ".iso"},
    "executables":{".exe", ".app", ".msi", ".deb", ".rpm", ".pkg"},
    "fonts":      {".ttf", ".otf", ".woff", ".woff2", ".eot"},
}


def setup_logging(verbose: bool = False) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        format="%(asctime)s  %(levelname)-8s  %(message)s",
        datefmt="%H:%M:%S",
        level=level,
        handlers=[
            logging.StreamHandler(sys.stdout),
        ],
    )


def get_category(suffix: str) -> str:
    """Return the folder name for a given file extension, or 'misc' if unknown."""
    suffix = suffix.lower()
    for category, extensions in FILE_CATEGORIES.items():
        if suffix in extensions:
            return category
    return "misc"


def resolve_destination(dest_dir: Path, filename: str) -> Path:
    """Return a unique destination path, appending a counter if the name is taken."""
    dest = dest_dir / filename
    if not dest.exists():
        return dest
    stem = Path(filename).stem
    suffix = Path(filename).suffix
    counter = 1
    while dest.exists():
        dest = dest_dir / f"{stem} ({counter}){suffix}"
        counter += 1
    return dest


def format_size(num_bytes: int) -> str:
    """Return a human-readable file size string."""
    for unit in ("B", "KB", "MB", "GB"):
        if num_bytes < 1024:
            return f"{num_bytes:.1f} {unit}"
        num_bytes /= 1024
    return f"{num_bytes:.1f} TB"


# Each category entry: {"count": int, "size_bytes": int, "files": [str, ...]}
Summary = dict[str, dict]


def organize(target: Path, dry_run: bool = False) -> tuple[Summary, list[dict]]:
    """
    Move files in *target* into categorized subdirectories.

    Returns (summary, moves) where summary is {category: {count, size_bytes, files}}
    and moves is a list of {"from": rel_src, "to": rel_dest} dicts for each successful move.
    """
    if not target.exists():
        raise FileNotFoundError(f"Directory not found: {target}")
    if not target.is_dir():
        raise NotADirectoryError(f"Path is not a directory: {target}")

    summary: Summary = {}
    moves: list[dict] = []
    files = [p for p in target.iterdir() if p.is_file() and not p.name.startswith(".")]

    if not files:
        logging.info("No files found in %s", target)
        return summary, moves

    logging.info("Found %d file(s) in %s", len(files), target)

    for file_path in files:
        category = get_category(file_path.suffix)
        dest_dir = target / category
        dest_path = resolve_destination(dest_dir, file_path.name)
        file_size = file_path.stat().st_size

        entry = summary.setdefault(category, {"count": 0, "size_bytes": 0, "files": []})

        if dry_run:
            logging.info("[DRY RUN] Would move: %s  →  %s", file_path.name, dest_path.relative_to(target))
            entry["count"] += 1
            entry["size_bytes"] += file_size
            entry["files"].append(file_path.name)
            continue

        try:
            dest_dir.mkdir(exist_ok=True)
            shutil.move(str(file_path), str(dest_path))
            logging.info("Moved: %s  →  %s", file_path.name, dest_path.relative_to(target))
            entry["count"] += 1
            entry["size_bytes"] += file_size
            entry["files"].append(file_path.name)
            moves.append({
                "from": file_path.name,
                "to": str(dest_path.relative_to(target)),
            })
        except PermissionError:
            logging.error("Permission denied: %s — skipping", file_path.name)
        except OSError as exc:
            logging.error("Failed to move %s: %s — skipping", file_path.name, exc)

    return summary, moves


def save_undo_manifest(moves: list[dict], target: Path) -> None:
    """Write a manifest of the last organize run so it can be undone."""
    manifest = {
        "organized_at": datetime.now().isoformat(timespec="seconds"),
        "directory": str(target),
        "moves": moves,
    }
    (target / UNDO_FILE).write_text(json.dumps(manifest, indent=2))
    logging.info("Undo manifest saved to %s", target / UNDO_FILE)


def _append_to_log(log_path: Path, entry: dict) -> None:
    """Append an entry to a JSON-array log file, creating it if needed."""
    log_path.parent.mkdir(parents=True, exist_ok=True)
    history: list[dict] = []
    if log_path.exists():
        try:
            history = json.loads(log_path.read_text())
        except (json.JSONDecodeError, ValueError):
            logging.warning("Could not parse log %s; starting fresh", log_path)
    history.append(entry)
    log_path.write_text(json.dumps(history, indent=2))


def append_history_log(summary: Summary, target: Path) -> None:
    """Append an organize record to the target directory's history log."""
    entry = {
        "type": "organize",
        "run_at": datetime.now().isoformat(timespec="seconds"),
        "files_moved": sum(e["count"] for e in summary.values()),
        "size_bytes": sum(e["size_bytes"] for e in summary.values()),
        "categories": {cat: e["count"] for cat, e in summary.items()},
    }
    log_path = target / HISTORY_FILE
    _append_to_log(log_path, entry)
    logging.info("Run appended to history log %s", log_path)


def append_central_log(summary: Summary, target: Path, log_path: Optional[Path] = None) -> None:
    """Append an organize record to the machine-wide central log."""
    if log_path is None:
        log_path = CENTRAL_LOG
    entry = {
        "type": "organize",
        "run_at": datetime.now().isoformat(timespec="seconds"),
        "directory": str(target),
        "files_moved": sum(e["count"] for e in summary.values()),
        "size_bytes": sum(e["size_bytes"] for e in summary.values()),
        "categories": {cat: e["count"] for cat, e in summary.items()},
    }
    _append_to_log(log_path, entry)
    logging.info("Run appended to central log %s", log_path)


def undo(target: Path, dry_run: bool = False, central_log_path: Optional[Path] = None) -> None:
    """Reverse the last organize run using the undo manifest."""
    if central_log_path is None:
        central_log_path = CENTRAL_LOG
    manifest_path = target / UNDO_FILE
    if not manifest_path.exists():
        logging.error("No undo manifest found in %s — nothing to undo", target)
        sys.exit(1)

    manifest = json.loads(manifest_path.read_text())
    moves: list[dict] = manifest["moves"]

    if not moves:
        logging.info("Nothing to undo.")
        return

    logging.info("Undoing %d move(s) from %s", len(moves), manifest["organized_at"])

    restored = 0
    for move in moves:
        src = target / move["to"]
        dest = target / move["from"]

        if not src.exists():
            logging.warning("File not found, skipping: %s", move["to"])
            continue

        if dry_run:
            logging.info("[DRY RUN] Would restore: %s  →  %s", move["to"], move["from"])
            restored += 1
            continue

        try:
            dest_path = resolve_destination(dest.parent, dest.name)
            if dest_path != dest:
                logging.warning("Name conflict for %s; saving as %s", move["from"], dest_path.name)
            shutil.move(str(src), str(dest_path))
            logging.info("Restored: %s  →  %s", move["to"], dest_path.name)
            restored += 1
        except OSError as exc:
            logging.error("Failed to restore %s: %s — skipping", move["from"], exc)

    if dry_run:
        logging.info("[DRY RUN] Would restore %d file(s)", restored)
        return

    dirs_removed = 0
    for move in moves:
        cat_dir = target / Path(move["to"]).parent
        if cat_dir != target and cat_dir.is_dir() and not any(cat_dir.iterdir()):
            cat_dir.rmdir()
            dirs_removed += 1

    manifest_path.unlink()
    logging.info("Undo complete: %d file(s) restored, %d empty dir(s) removed", restored, dirs_removed)

    now = datetime.now().isoformat(timespec="seconds")
    _append_to_log(target / HISTORY_FILE, {
        "type": "undo",
        "run_at": now,
        "files_restored": restored,
    })
    logging.info("Undo appended to history log %s", target / HISTORY_FILE)
    _append_to_log(central_log_path, {
        "type": "undo",
        "run_at": now,
        "directory": str(target),
        "files_restored": restored,
    })
    logging.info("Undo appended to central log %s", central_log_path)


def print_summary(summary: Summary, dry_run: bool) -> None:
    prefix = "[DRY RUN] " if dry_run else ""
    print()
    print(f"{prefix}--- Summary Report ---")
    if not summary:
        print("  Nothing to organize.")
        return
    total_count = sum(e["count"] for e in summary.values())
    total_bytes = sum(e["size_bytes"] for e in summary.values())
    print(f"  {'Category':<14}  {'Files':>6}  {'Size':>10}")
    print(f"  {'-'*14}  {'-'*6}  {'-'*10}")
    for category, entry in sorted(summary.items()):
        size_str = format_size(entry["size_bytes"])
        print(f"  {category:<14}  {entry['count']:>6}  {size_str:>10}")
    print(f"  {'-'*14}  {'-'*6}  {'-'*10}")
    print(f"  {'TOTAL':<14}  {total_count:>6}  {format_size(total_bytes):>10}")


def print_history(log_path: Path = CENTRAL_LOG, directory: Optional[Path] = None) -> None:
    """Print a human-readable summary of a run history log."""
    if not log_path.exists():
        print("No history found. Run the organizer on a directory first.")
        return
    try:
        entries = json.loads(log_path.read_text())
    except (json.JSONDecodeError, ValueError):
        print(f"Could not parse history log: {log_path}")
        return
    if not entries:
        print("History log is empty.")
        return
    print(f"\n--- Organizer History ({len(entries)} entries) ---\n")
    for e in entries:
        entry_type = e.get("type", "organize")
        timestamp = e.get("run_at", "unknown")
        dir_label = e.get("directory") or (str(directory) if directory else "unknown")
        if entry_type == "organize":
            detail = f"{e.get('files_moved', 0)} files moved"
        else:
            detail = f"{e.get('files_restored', 0)} files restored"
        print(f"  {timestamp}  [{entry_type:<8}]  {detail:<20}  {dir_label}")
    print()


def save_report(summary: Summary, target: Path, report_path: Path, dry_run: bool) -> None:
    report = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "directory": str(target),
        "dry_run": dry_run,
        "totals": {
            "files": sum(e["count"] for e in summary.values()),
            "size_bytes": sum(e["size_bytes"] for e in summary.values()),
        },
        "categories": {
            cat: {
                "count": e["count"],
                "size_bytes": e["size_bytes"],
                "size_human": format_size(e["size_bytes"]),
                "files": sorted(e["files"]),
            }
            for cat, e in sorted(summary.items())
        },
    }
    report_path.write_text(json.dumps(report, indent=2))
    logging.info("Report saved to %s", report_path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Organize files in a directory into categorized subfolders."
    )
    parser.add_argument("directory", nargs="?", help="Path to the directory to organize")
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Preview changes without moving any files"
    )
    parser.add_argument(
        "--undo", action="store_true",
        help="Restore files to their original locations using the last run's manifest"
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true",
        help="Enable debug-level logging"
    )
    parser.add_argument(
        "--report", metavar="FILE",
        help="Save a JSON summary report to FILE (e.g. report.json)"
    )
    parser.add_argument(
        "--history", action="store_true",
        help="Show the history of all organizer runs on this machine"
    )
    parser.add_argument(
        "--version", action="version", version=f"%(prog)s {VERSION}"
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    setup_logging(args.verbose)

    if args.history:
        if args.directory:
            target = Path(args.directory).expanduser().resolve()
            print_history(target / HISTORY_FILE, directory=target)
        else:
            print_history()
        return

    if not args.directory:
        logging.error("A directory is required unless using --history")
        sys.exit(1)

    target = Path(args.directory).expanduser().resolve()
    logging.info("Target directory: %s", target)
    if args.dry_run:
        logging.info("Dry-run mode enabled — no files will be moved")

    if args.undo:
        undo(target, dry_run=args.dry_run)
        return

    try:
        summary, moves = organize(target, dry_run=args.dry_run)
    except (FileNotFoundError, NotADirectoryError) as exc:
        logging.error("%s", exc)
        sys.exit(1)

    print_summary(summary, dry_run=args.dry_run)

    if args.report:
        save_report(summary, target, Path(args.report), dry_run=args.dry_run)

    if not args.dry_run and moves:
        save_undo_manifest(moves, target)
        append_history_log(summary, target)
        append_central_log(summary, target)


if __name__ == "__main__":
    main()
