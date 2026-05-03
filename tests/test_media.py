"""Tests for media enrichment — PDF page counts, durations, and caching."""

import shutil
from pathlib import Path
from unittest.mock import patch

import pytest
from pypdf import PdfWriter

from mediastudyshelf.core.content.probe import (
    _cache,
    clear_cache,
    get_media_duration,
    get_pdf_page_count,
)


@pytest.fixture(autouse=True)
def _fresh_cache():
    """Ensure each test starts with an empty cache."""
    clear_cache()
    yield
    clear_cache()


@pytest.fixture
def tiny_pdf(tmp_path: Path) -> Path:
    """Create a real 4-page PDF."""
    path = tmp_path / "test.pdf"
    writer = PdfWriter()
    for _ in range(4):
        writer.add_blank_page(width=612, height=792)
    with open(path, "wb") as f:
        writer.write(f)
    return path


@pytest.fixture
def corrupt_pdf(tmp_path: Path) -> Path:
    """Create a file that looks like a PDF but isn't valid."""
    path = tmp_path / "bad.pdf"
    path.write_bytes(b"not a real pdf")
    return path


# ── PDF page count tests ───────────────────────────────────────────────────


def test_pdf_page_count(tiny_pdf: Path):
    assert get_pdf_page_count(tiny_pdf) == 4


def test_corrupt_pdf_returns_none(corrupt_pdf: Path):
    result = get_pdf_page_count(corrupt_pdf)
    assert result is None


# ── Duration tests (only run if ffprobe is available) ──────────────────────

_has_ffprobe = shutil.which("ffprobe") is not None


@pytest.fixture
def tiny_audio(tmp_path: Path) -> Path | None:
    """Generate a 2-second sine wave MP3 via ffmpeg, if available."""
    if not shutil.which("ffmpeg"):
        pytest.skip("ffmpeg not installed")
    import subprocess

    path = tmp_path / "tone.mp3"
    subprocess.run(
        [
            "ffmpeg", "-y", "-f", "lavfi",
            "-i", "sine=frequency=440:duration=2",
            "-c:a", "libmp3lame", "-b:a", "64k",
            str(path),
        ],
        capture_output=True,
    )
    return path


@pytest.mark.skipif(not _has_ffprobe, reason="ffprobe not installed")
def test_audio_duration(tiny_audio: Path):
    duration = get_media_duration(tiny_audio)
    assert duration is not None
    assert 1 <= duration <= 3  # ~2 seconds, allow rounding


@pytest.mark.skipif(not _has_ffprobe, reason="ffprobe not installed")
def test_duration_missing_file(tmp_path: Path):
    fake = tmp_path / "nonexistent.mp3"
    fake.write_bytes(b"not audio")
    result = get_media_duration(fake)
    assert result is None


# ── Cache test ─────────────────────────────────────────────────────────────


def test_cache_prevents_recomputation(tiny_pdf: Path):
    """Second call must hit cache, not re-invoke pypdf."""
    # First call — populates cache
    result1 = get_pdf_page_count(tiny_pdf)
    assert result1 == 4
    assert len(_cache) == 1

    # Patch PdfReader so any real call would blow up
    with patch("mediastudyshelf.core.content.probe.PdfReader", side_effect=AssertionError("should not be called")):
        result2 = get_pdf_page_count(tiny_pdf)

    assert result2 == 4  # same result, from cache
