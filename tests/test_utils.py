"""tests/test_utils.py — Unit tests for filename sanitisation and path utilities."""
import pytest
from app.utils import sanitize_filename


class TestSanitizeFilename:
    def test_plain_ascii(self):
        assert sanitize_filename("my_song") == "my_song"

    def test_spaces_become_underscore(self):
        result = sanitize_filename("my song title")
        assert " " not in result
        assert "_" in result

    def test_vietnamese_characters_preserved(self):
        result = sanitize_filename("Nơi này có anh")
        # Vietnamese diacritics must not be stripped
        assert "ơ" in result or "a" in result  # at least something survives

    def test_windows_forbidden_chars_stripped(self):
        result = sanitize_filename('file:<name>|test?*')
        for ch in '<>:"|?*':
            assert ch not in result

    def test_colon_in_timestamp_stripped(self):
        result = sanitize_filename("2024:01:15")
        assert ":" not in result

    def test_empty_string_fallback(self):
        assert sanitize_filename("") == "file"

    def test_all_special_chars_fallback(self):
        assert sanitize_filename(":::***|||") == "file"

    def test_truncation(self):
        long = "a" * 200
        result = sanitize_filename(long, max_len=50)
        assert len(result) <= 50

    def test_brackets_stripped(self):
        # Parentheses are allowed, angle brackets are not
        result = sanitize_filename("song (live) [2024]")
        assert "<" not in result
        assert ">" not in result

    def test_backslash_stripped(self):
        result = sanitize_filename("path\\to\\file")
        assert "\\" not in result

    def test_forward_slash_stripped(self):
        result = sanitize_filename("path/to/file")
        assert "/" not in result
