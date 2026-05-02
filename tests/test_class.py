"""Tests for GET /api/class/{courseSlug}/{moduleSlug}/{classSlug}."""

import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

SAMPLE_CONTENT = str(Path(__file__).resolve().parent / "sample-content")
os.environ["MEDIASTUDYSHELF_CONTENT_PATH"] = SAMPLE_CONTENT

from mediastudyshelf.main import app  # noqa: E402


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


# ── Happy path ─────────────────────────────────────────────────────────────


def test_class_full_response_shape(client):
    """Fetch a class with multiple PDFs, audio, and extras — verify full shape."""
    resp = client.get("/api/class/intro-to-systems-thinking/foundations/feedback-loops")
    assert resp.status_code == 200
    data = resp.json()

    # Top-level keys
    assert set(data.keys()) == {"course", "module", "class", "nav"}

    # Course ref
    assert data["course"]["slug"] == "intro-to-systems-thinking"
    assert data["course"]["title"] == "Intro to systems thinking"

    # Module ref
    assert data["module"]["slug"] == "foundations"
    assert data["module"]["number"] == 1

    # Class detail
    cls = data["class"]
    assert cls["slug"] == "feedback-loops"
    assert cls["number"] == 2

    # Video
    assert cls["video"] is not None
    assert cls["video"]["url"].startswith("/media/assets/")
    assert cls["video"]["url"].endswith("/video.mp4")
    assert isinstance(cls["video"]["duration_seconds"], int)

    # PDFs — 3 total, exactly one primary
    assert len(cls["pdfs"]) == 3
    primaries = [p for p in cls["pdfs"] if p["is_primary"]]
    assert len(primaries) == 1
    assert primaries[0]["filename"] == "lesson-notes.pdf"
    for pdf in cls["pdfs"]:
        assert "filename" in pdf
        assert pdf["url"].startswith("/media/assets/")
        assert isinstance(pdf["pages"], int)
        assert isinstance(pdf["size_bytes"], int)

    # Audio
    assert len(cls["audio"]) == 2
    for a in cls["audio"]:
        assert "filename" in a
        assert "label" in a
        assert a["url"].startswith("/media/assets/")

    # Audio label override from class.json
    qa = next(a for a in cls["audio"] if a["filename"] == "q-and-a.mp3")
    assert qa["label"] == "Q&A session"

    # Extras
    assert len(cls["extras"]) == 1
    assert cls["extras"][0]["filename"] == "resources.zip"
    assert isinstance(cls["extras"][0]["size_bytes"], int)


# ── 404 cases ──────────────────────────────────────────────────────────────


def test_404_bad_course_slug(client):
    resp = client.get("/api/class/nonexistent/foundations/feedback-loops")
    assert resp.status_code == 404


def test_404_bad_module_slug(client):
    resp = client.get("/api/class/intro-to-systems-thinking/nonexistent/feedback-loops")
    assert resp.status_code == 404


def test_404_bad_class_slug(client):
    resp = client.get("/api/class/intro-to-systems-thinking/foundations/nonexistent")
    assert resp.status_code == 404


# ── Prev/next navigation ──────────────────────────────────────────────────


def test_nav_first_class_has_no_prev(client):
    """First class in the course — prev is null, next is set."""
    resp = client.get("/api/class/intro-to-systems-thinking/foundations/what-is-a-system")
    data = resp.json()
    assert data["nav"]["prev"] is None
    assert data["nav"]["next"] is not None
    assert data["nav"]["next"]["class"] == "feedback-loops"


def test_nav_last_class_has_no_next(client):
    """Last class in the course — prev is set, next is null."""
    resp = client.get("/api/class/intro-to-systems-thinking/modeling/building-a-model")
    data = resp.json()
    assert data["nav"]["prev"] is not None
    assert data["nav"]["next"] is None


def test_nav_middle_class_has_both(client):
    """Middle class — both prev and next set."""
    resp = client.get("/api/class/intro-to-systems-thinking/foundations/feedback-loops")
    data = resp.json()
    assert data["nav"]["prev"] is not None
    assert data["nav"]["next"] is not None
    assert data["nav"]["prev"]["class"] == "what-is-a-system"


def test_nav_cross_module(client):
    """Last class of module 1 → next should be first class of module 2."""
    resp = client.get("/api/class/intro-to-systems-thinking/foundations/video-only-class")
    data = resp.json()
    next_nav = data["nav"]["next"]
    assert next_nav is not None
    assert next_nav["module"] == "modeling"
    assert next_nav["class"] == "building-a-model"
