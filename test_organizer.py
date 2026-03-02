"""
Tests for organizer.py
Run with: python3 -m pytest test_organizer.py -v
"""

import json
import tempfile
from pathlib import Path

import pytest

import organizer
from organizer import (
    HISTORY_FILE,
    UNDO_FILE,
    append_central_log,
    append_history_log,
    format_size,
    get_category,
    organize,
    resolve_destination,
    save_report,
    save_undo_manifest,
    undo,
)


# ---------------------------------------------------------------------------
# get_category
# ---------------------------------------------------------------------------

class TestGetCategory:
    def test_known_image_extensions(self):
        assert get_category(".jpg") == "images"
        assert get_category(".png") == "images"
        assert get_category(".heic") == "images"

    def test_known_video_extensions(self):
        assert get_category(".mp4") == "videos"
        assert get_category(".mov") == "videos"

    def test_known_audio_extensions(self):
        assert get_category(".mp3") == "audio"
        assert get_category(".flac") == "audio"

    def test_known_document_extensions(self):
        assert get_category(".pdf") == "documents"
        assert get_category(".docx") == "documents"
        assert get_category(".xlsx") == "documents"

    def test_known_text_extensions(self):
        assert get_category(".txt") == "text"
        assert get_category(".md") == "text"
        assert get_category(".csv") == "text"

    def test_known_code_extensions(self):
        assert get_category(".py") == "code"
        assert get_category(".js") == "code"
        assert get_category(".yaml") == "code"

    def test_known_archive_extensions(self):
        assert get_category(".zip") == "archives"
        assert get_category(".tar") == "archives"
        assert get_category(".gz") == "archives"

    def test_known_font_extensions(self):
        assert get_category(".ttf") == "fonts"
        assert get_category(".woff") == "fonts"

    def test_unknown_extension_returns_misc(self):
        assert get_category(".xyz") == "misc"
        assert get_category(".foobar") == "misc"

    def test_no_extension_returns_misc(self):
        assert get_category("") == "misc"

    def test_case_insensitive(self):
        assert get_category(".JPG") == "images"
        assert get_category(".PNG") == "images"
        assert get_category(".MP4") == "videos"
        assert get_category(".PY") == "code"


# ---------------------------------------------------------------------------
# format_size
# ---------------------------------------------------------------------------

class TestFormatSize:
    def test_bytes(self):
        assert format_size(0) == "0.0 B"
        assert format_size(512) == "512.0 B"
        assert format_size(1023) == "1023.0 B"

    def test_kilobytes(self):
        assert format_size(1024) == "1.0 KB"
        assert format_size(2048) == "2.0 KB"

    def test_megabytes(self):
        assert format_size(1024 ** 2) == "1.0 MB"
        assert format_size(5 * 1024 ** 2) == "5.0 MB"

    def test_gigabytes(self):
        assert format_size(1024 ** 3) == "1.0 GB"

    def test_terabytes(self):
        assert format_size(1024 ** 4) == "1.0 TB"


# ---------------------------------------------------------------------------
# resolve_destination
# ---------------------------------------------------------------------------

class TestResolveDestination:
    def test_no_collision_returns_plain_path(self, tmp_path):
        dest = resolve_destination(tmp_path, "file.txt")
        assert dest == tmp_path / "file.txt"

    def test_first_collision_appends_one(self, tmp_path):
        (tmp_path / "file.txt").touch()
        dest = resolve_destination(tmp_path, "file.txt")
        assert dest == tmp_path / "file (1).txt"

    def test_second_collision_appends_two(self, tmp_path):
        (tmp_path / "file.txt").touch()
        (tmp_path / "file (1).txt").touch()
        dest = resolve_destination(tmp_path, "file.txt")
        assert dest == tmp_path / "file (2).txt"

    def test_no_extension_file(self, tmp_path):
        (tmp_path / "mystery").touch()
        dest = resolve_destination(tmp_path, "mystery")
        assert dest == tmp_path / "mystery (1)"

    def test_dest_dir_need_not_exist(self, tmp_path):
        nonexistent = tmp_path / "subdir"
        dest = resolve_destination(nonexistent, "file.txt")
        assert dest == nonexistent / "file.txt"


# ---------------------------------------------------------------------------
# organize
# ---------------------------------------------------------------------------

class TestOrganize:
    def _make_files(self, directory: Path, names: list[str], size: int = 16) -> None:
        for name in names:
            (directory / name).write_bytes(b"x" * size)

    def test_files_moved_to_correct_categories(self, tmp_path):
        self._make_files(tmp_path, ["photo.jpg", "song.mp3", "script.py", "notes.txt"])
        organize(tmp_path)
        assert (tmp_path / "images" / "photo.jpg").exists()
        assert (tmp_path / "audio" / "song.mp3").exists()
        assert (tmp_path / "code" / "script.py").exists()
        assert (tmp_path / "text" / "notes.txt").exists()

    def test_unknown_extension_goes_to_misc(self, tmp_path):
        self._make_files(tmp_path, ["mystery"])
        organize(tmp_path)
        assert (tmp_path / "misc" / "mystery").exists()

    def test_original_files_removed_from_root(self, tmp_path):
        self._make_files(tmp_path, ["photo.jpg", "script.py"])
        organize(tmp_path)
        assert not (tmp_path / "photo.jpg").exists()
        assert not (tmp_path / "script.py").exists()

    def test_summary_counts_are_correct(self, tmp_path):
        self._make_files(tmp_path, ["a.jpg", "b.jpg", "c.mp3"])
        summary, _ = organize(tmp_path)
        assert summary["images"]["count"] == 2
        assert summary["audio"]["count"] == 1

    def test_summary_size_bytes_are_correct(self, tmp_path):
        self._make_files(tmp_path, ["a.jpg", "b.jpg"], size=100)
        summary, _ = organize(tmp_path)
        assert summary["images"]["size_bytes"] == 200

    def test_summary_files_list(self, tmp_path):
        self._make_files(tmp_path, ["a.jpg", "b.jpg"])
        summary, _ = organize(tmp_path)
        assert set(summary["images"]["files"]) == {"a.jpg", "b.jpg"}

    def test_empty_directory_returns_empty_summary(self, tmp_path):
        summary, moves = organize(tmp_path)
        assert summary == {}
        assert moves == []

    def test_nonexistent_path_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            organize(tmp_path / "does_not_exist")

    def test_file_path_raises_not_a_directory(self, tmp_path):
        f = tmp_path / "file.txt"
        f.write_text("hi")
        with pytest.raises(NotADirectoryError):
            organize(f)

    def test_dry_run_does_not_move_files(self, tmp_path):
        self._make_files(tmp_path, ["photo.jpg", "notes.txt"])
        organize(tmp_path, dry_run=True)
        assert (tmp_path / "photo.jpg").exists()
        assert (tmp_path / "notes.txt").exists()
        assert not (tmp_path / "images").exists()
        assert not (tmp_path / "text").exists()

    def test_dry_run_summary_is_accurate(self, tmp_path):
        self._make_files(tmp_path, ["a.jpg", "b.jpg", "c.mp3"], size=50)
        summary, _ = organize(tmp_path, dry_run=True)
        assert summary["images"]["count"] == 2
        assert summary["images"]["size_bytes"] == 100
        assert summary["audio"]["count"] == 1
        assert summary["audio"]["size_bytes"] == 50

    def test_collision_does_not_overwrite(self, tmp_path):
        self._make_files(tmp_path, ["photo.jpg"])
        organize(tmp_path)
        # Put another photo.jpg in root and organize again
        (tmp_path / "photo.jpg").write_bytes(b"y" * 16)
        organize(tmp_path)
        assert (tmp_path / "images" / "photo.jpg").exists()
        assert (tmp_path / "images" / "photo (1).jpg").exists()

    def test_subdirectories_are_not_moved(self, tmp_path):
        subdir = tmp_path / "my_folder"
        subdir.mkdir()
        self._make_files(tmp_path, ["photo.jpg"])
        organize(tmp_path)
        assert (tmp_path / "my_folder").is_dir()

    def test_dotfiles_are_not_moved(self, tmp_path):
        for name in [".hidden", ".organizer_undo.json", ".organizer_history.json"]:
            (tmp_path / name).write_bytes(b"x")
        self._make_files(tmp_path, ["photo.jpg"])
        organize(tmp_path)
        for name in [".hidden", ".organizer_undo.json", ".organizer_history.json"]:
            assert (tmp_path / name).exists()
        assert not (tmp_path / "misc" / ".hidden").exists()


# ---------------------------------------------------------------------------
# save_report
# ---------------------------------------------------------------------------

class TestSaveReport:
    def _make_summary(self) -> dict:
        return {
            "images": {"count": 2, "size_bytes": 2048, "files": ["a.jpg", "b.png"]},
            "code":   {"count": 1, "size_bytes": 512,  "files": ["script.py"]},
        }

    def test_report_file_is_created(self, tmp_path):
        report_path = tmp_path / "report.json"
        save_report(self._make_summary(), tmp_path, report_path, dry_run=False)
        assert report_path.exists()

    def test_report_is_valid_json(self, tmp_path):
        report_path = tmp_path / "report.json"
        save_report(self._make_summary(), tmp_path, report_path, dry_run=False)
        data = json.loads(report_path.read_text())
        assert isinstance(data, dict)

    def test_report_top_level_keys(self, tmp_path):
        report_path = tmp_path / "report.json"
        save_report(self._make_summary(), tmp_path, report_path, dry_run=False)
        data = json.loads(report_path.read_text())
        for key in ("generated_at", "directory", "dry_run", "totals", "categories"):
            assert key in data

    def test_report_totals(self, tmp_path):
        report_path = tmp_path / "report.json"
        save_report(self._make_summary(), tmp_path, report_path, dry_run=False)
        data = json.loads(report_path.read_text())
        assert data["totals"]["files"] == 3
        assert data["totals"]["size_bytes"] == 2560

    def test_report_category_details(self, tmp_path):
        report_path = tmp_path / "report.json"
        save_report(self._make_summary(), tmp_path, report_path, dry_run=False)
        data = json.loads(report_path.read_text())
        images = data["categories"]["images"]
        assert images["count"] == 2
        assert images["size_bytes"] == 2048
        assert images["size_human"] == "2.0 KB"
        assert images["files"] == ["a.jpg", "b.png"]

    def test_report_dry_run_flag(self, tmp_path):
        report_path = tmp_path / "report.json"
        save_report(self._make_summary(), tmp_path, report_path, dry_run=True)
        data = json.loads(report_path.read_text())
        assert data["dry_run"] is True

    def test_report_directory_field(self, tmp_path):
        report_path = tmp_path / "report.json"
        save_report(self._make_summary(), tmp_path, report_path, dry_run=False)
        data = json.loads(report_path.read_text())
        assert data["directory"] == str(tmp_path)


# ---------------------------------------------------------------------------
# save_undo_manifest / undo
# ---------------------------------------------------------------------------

class TestUndo:
    def _make_files(self, directory: Path, names: list[str]) -> None:
        for name in names:
            (directory / name).write_bytes(b"x" * 16)

    def _organize_and_save(self, tmp_path):
        """Helper: run organize and write the undo manifest (mirrors what main() does)."""
        summary, moves = organize(tmp_path)
        save_undo_manifest(moves, tmp_path)
        return summary, moves

    def _undo(self, tmp_path, **kwargs):
        """Helper: run undo with a local central log to avoid touching the real one."""
        kwargs.setdefault("central_log_path", tmp_path / "central.json")
        return undo(tmp_path, **kwargs)

    def test_organize_writes_undo_manifest(self, tmp_path):
        self._make_files(tmp_path, ["photo.jpg", "notes.txt"])
        self._organize_and_save(tmp_path)
        assert (tmp_path / UNDO_FILE).exists()

    def test_manifest_contains_expected_moves(self, tmp_path):
        self._make_files(tmp_path, ["photo.jpg"])
        self._organize_and_save(tmp_path)
        data = json.loads((tmp_path / UNDO_FILE).read_text())
        assert len(data["moves"]) == 1
        assert data["moves"][0]["from"] == "photo.jpg"
        assert data["moves"][0]["to"] == "images/photo.jpg"

    def test_undo_restores_files_to_root(self, tmp_path):
        self._make_files(tmp_path, ["photo.jpg", "notes.txt"])
        self._organize_and_save(tmp_path)
        self._undo(tmp_path)
        assert (tmp_path / "photo.jpg").exists()
        assert (tmp_path / "notes.txt").exists()

    def test_undo_removes_empty_category_dirs(self, tmp_path):
        self._make_files(tmp_path, ["photo.jpg"])
        self._organize_and_save(tmp_path)
        self._undo(tmp_path)
        assert not (tmp_path / "images").exists()

    def test_undo_keeps_non_empty_category_dirs(self, tmp_path):
        self._make_files(tmp_path, ["photo.jpg"])
        self._organize_and_save(tmp_path)
        # drop an extra file into the category dir so it's not empty
        (tmp_path / "images" / "extra.jpg").write_bytes(b"y" * 16)
        self._undo(tmp_path)
        assert (tmp_path / "images").exists()

    def test_undo_deletes_manifest_after_restore(self, tmp_path):
        self._make_files(tmp_path, ["photo.jpg"])
        self._organize_and_save(tmp_path)
        self._undo(tmp_path)
        assert not (tmp_path / UNDO_FILE).exists()

    def test_undo_dry_run_does_not_move_files(self, tmp_path):
        self._make_files(tmp_path, ["photo.jpg"])
        self._organize_and_save(tmp_path)
        self._undo(tmp_path, dry_run=True)
        assert (tmp_path / "images" / "photo.jpg").exists()
        assert not (tmp_path / "photo.jpg").exists()

    def test_undo_dry_run_keeps_manifest(self, tmp_path):
        self._make_files(tmp_path, ["photo.jpg"])
        self._organize_and_save(tmp_path)
        self._undo(tmp_path, dry_run=True)
        assert (tmp_path / UNDO_FILE).exists()

    def test_undo_missing_manifest_exits(self, tmp_path):
        import pytest
        with pytest.raises(SystemExit):
            undo(tmp_path, central_log_path=tmp_path / "central.json")

    def test_undo_skips_missing_files_and_continues(self, tmp_path):
        self._make_files(tmp_path, ["photo.jpg", "notes.txt"])
        self._organize_and_save(tmp_path)
        # Simulate file gone since organize ran
        (tmp_path / "images" / "photo.jpg").unlink()
        self._undo(tmp_path)  # should not raise
        assert (tmp_path / "notes.txt").exists()

    def test_dry_run_organize_does_not_write_manifest(self, tmp_path):
        self._make_files(tmp_path, ["photo.jpg"])
        organize(tmp_path, dry_run=True)
        assert not (tmp_path / UNDO_FILE).exists()

    def test_undo_appends_to_history_log(self, tmp_path):
        self._make_files(tmp_path, ["photo.jpg"])
        self._organize_and_save(tmp_path)
        undo(tmp_path, central_log_path=tmp_path / "central.json")
        data = json.loads((tmp_path / HISTORY_FILE).read_text())
        types = [e["type"] for e in data]
        assert "undo" in types

    def test_undo_history_entry_has_expected_keys(self, tmp_path):
        self._make_files(tmp_path, ["photo.jpg"])
        self._organize_and_save(tmp_path)
        undo(tmp_path, central_log_path=tmp_path / "central.json")
        entries = json.loads((tmp_path / HISTORY_FILE).read_text())
        undo_entry = next(e for e in entries if e["type"] == "undo")
        for key in ("type", "run_at", "files_restored"):
            assert key in undo_entry

    def test_undo_appends_to_central_log(self, tmp_path):
        self._make_files(tmp_path, ["photo.jpg"])
        self._organize_and_save(tmp_path)
        central = tmp_path / "central.json"
        undo(tmp_path, central_log_path=central)
        data = json.loads(central.read_text())
        types = [e["type"] for e in data]
        assert "undo" in types

    def test_undo_central_entry_has_directory(self, tmp_path):
        self._make_files(tmp_path, ["photo.jpg"])
        self._organize_and_save(tmp_path)
        central = tmp_path / "central.json"
        undo(tmp_path, central_log_path=central)
        entries = json.loads(central.read_text())
        undo_entry = next(e for e in entries if e["type"] == "undo")
        assert undo_entry["directory"] == str(tmp_path)

    def test_undo_dry_run_does_not_log(self, tmp_path):
        self._make_files(tmp_path, ["photo.jpg"])
        self._organize_and_save(tmp_path)
        central = tmp_path / "central.json"
        undo(tmp_path, dry_run=True, central_log_path=central)
        assert not (tmp_path / HISTORY_FILE).exists() or all(
            e["type"] != "undo"
            for e in json.loads((tmp_path / HISTORY_FILE).read_text())
        )
        assert not central.exists()

    def test_save_undo_manifest_structure(self, tmp_path):
        moves = [{"from": "a.jpg", "to": "images/a.jpg"}]
        save_undo_manifest(moves, tmp_path)
        data = json.loads((tmp_path / UNDO_FILE).read_text())
        assert "organized_at" in data
        assert data["directory"] == str(tmp_path)
        assert data["moves"] == moves


# ---------------------------------------------------------------------------
# append_history_log
# ---------------------------------------------------------------------------

class TestAppendHistoryLog:
    def _make_summary(self, images: int = 2, audio: int = 1) -> dict:
        return {
            "images": {"count": images, "size_bytes": images * 1024, "files": []},
            "audio":  {"count": audio,  "size_bytes": audio * 512,   "files": []},
        }

    def test_history_file_created_on_first_run(self, tmp_path):
        append_history_log(self._make_summary(), tmp_path)
        assert (tmp_path / HISTORY_FILE).exists()

    def test_history_is_valid_json_array(self, tmp_path):
        append_history_log(self._make_summary(), tmp_path)
        data = json.loads((tmp_path / HISTORY_FILE).read_text())
        assert isinstance(data, list)

    def test_history_entry_has_expected_keys(self, tmp_path):
        append_history_log(self._make_summary(), tmp_path)
        entry = json.loads((tmp_path / HISTORY_FILE).read_text())[0]
        for key in ("type", "run_at", "files_moved", "size_bytes", "categories"):
            assert key in entry

    def test_history_entry_type_is_organize(self, tmp_path):
        append_history_log(self._make_summary(), tmp_path)
        entry = json.loads((tmp_path / HISTORY_FILE).read_text())[0]
        assert entry["type"] == "organize"

    def test_history_counts_match_summary(self, tmp_path):
        append_history_log(self._make_summary(images=3, audio=2), tmp_path)
        entry = json.loads((tmp_path / HISTORY_FILE).read_text())[0]
        assert entry["files_moved"] == 5
        assert entry["categories"] == {"images": 3, "audio": 2}

    def test_history_appends_on_multiple_runs(self, tmp_path):
        append_history_log(self._make_summary(), tmp_path)
        append_history_log(self._make_summary(), tmp_path)
        append_history_log(self._make_summary(), tmp_path)
        data = json.loads((tmp_path / HISTORY_FILE).read_text())
        assert len(data) == 3

    def test_history_not_written_on_dry_run(self, tmp_path):
        # dry-run is handled in main(); organize() + append_history_log()
        # should never be called together in dry-run. Verify the file
        # is absent if we simply never call append_history_log.
        assert not (tmp_path / HISTORY_FILE).exists()


# ---------------------------------------------------------------------------
# append_central_log
# ---------------------------------------------------------------------------

class TestAppendCentralLog:
    def _make_summary(self, images: int = 2, audio: int = 1) -> dict:
        return {
            "images": {"count": images, "size_bytes": images * 1024, "files": []},
            "audio":  {"count": audio,  "size_bytes": audio * 512,   "files": []},
        }

    def test_central_log_created_on_first_run(self, tmp_path):
        log = tmp_path / "central.json"
        append_central_log(self._make_summary(), tmp_path, log_path=log)
        assert log.exists()

    def test_central_log_creates_parent_dirs(self, tmp_path):
        log = tmp_path / "deep" / "nested" / "history.json"
        append_central_log(self._make_summary(), tmp_path, log_path=log)
        assert log.exists()

    def test_central_log_is_valid_json_array(self, tmp_path):
        log = tmp_path / "central.json"
        append_central_log(self._make_summary(), tmp_path, log_path=log)
        data = json.loads(log.read_text())
        assert isinstance(data, list)

    def test_central_log_entry_has_directory_field(self, tmp_path):
        log = tmp_path / "central.json"
        append_central_log(self._make_summary(), tmp_path, log_path=log)
        entry = json.loads(log.read_text())[0]
        assert entry["directory"] == str(tmp_path)

    def test_central_log_entry_has_expected_keys(self, tmp_path):
        log = tmp_path / "central.json"
        append_central_log(self._make_summary(), tmp_path, log_path=log)
        entry = json.loads(log.read_text())[0]
        for key in ("type", "run_at", "directory", "files_moved", "size_bytes", "categories"):
            assert key in entry

    def test_central_log_entry_type_is_organize(self, tmp_path):
        log = tmp_path / "central.json"
        append_central_log(self._make_summary(), tmp_path, log_path=log)
        entry = json.loads(log.read_text())[0]
        assert entry["type"] == "organize"

    def test_central_log_appends_across_directories(self, tmp_path):
        log = tmp_path / "central.json"
        dir_a = tmp_path / "dirA"
        dir_b = tmp_path / "dirB"
        append_central_log(self._make_summary(), dir_a, log_path=log)
        append_central_log(self._make_summary(), dir_b, log_path=log)
        data = json.loads(log.read_text())
        assert len(data) == 2
        assert data[0]["directory"] == str(dir_a)
        assert data[1]["directory"] == str(dir_b)


# ---------------------------------------------------------------------------
# platformdirs integration
# ---------------------------------------------------------------------------

class TestPlatformdirs:
    def _make_summary(self) -> dict:
        return {
            "images": {"count": 1, "size_bytes": 1024, "files": ["a.jpg"]},
        }

    def test_append_central_log_respects_central_log_constant(self, monkeypatch, tmp_path):
        """append_central_log() with no explicit path should use the CENTRAL_LOG constant."""
        fake_log = tmp_path / "fake_central.json"
        monkeypatch.setattr(organizer, "CENTRAL_LOG", fake_log)
        append_central_log(self._make_summary(), tmp_path)
        assert fake_log.exists()

    def test_undo_respects_central_log_constant(self, monkeypatch, tmp_path):
        """undo() with no explicit central_log_path should use the CENTRAL_LOG constant."""
        fake_log = tmp_path / "fake_central.json"
        monkeypatch.setattr(organizer, "CENTRAL_LOG", fake_log)
        # Set up an organize + manifest so undo has something to reverse
        (tmp_path / "photo.jpg").write_bytes(b"x" * 16)
        _, moves = organize(tmp_path)
        save_undo_manifest(moves, tmp_path)
        undo(tmp_path)
        assert fake_log.exists()
        data = json.loads(fake_log.read_text())
        assert data[0]["type"] == "undo"

    def test_central_log_path_comes_from_platformdirs(self, monkeypatch):
        """CENTRAL_LOG should be derived from platformdirs, not a hardcoded path."""
        from platformdirs import user_data_dir
        expected = Path(user_data_dir("organizer")) / "history.json"
        assert organizer.CENTRAL_LOG == expected
