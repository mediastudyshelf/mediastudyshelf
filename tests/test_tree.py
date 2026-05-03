"""Tests for GET /api/tree using the sample-content fixture."""

import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

# Point at sample-content before importing the app
SAMPLE_CONTENT = str(Path(__file__).resolve().parent / "sample-content")
os.environ["MEDIASTUDYSHELF_CONTENT_PATH"] = SAMPLE_CONTENT

from mediastudyshelf.main import app  # noqa: E402


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def test_tree_returns_200(client):
    resp = client.get("/api/tree")
    assert resp.status_code == 200


def test_tree_structure(client):
    resp = client.get("/api/tree")
    data = resp.json()

    # Top level
    assert "courses" in data
    assert len(data["courses"]) == 1

    course = data["courses"][0]
    assert course["slug"] == "intro-to-systems-thinking"
    assert course["title"] == "Intro to systems thinking"

    # Modules
    assert len(course["modules"]) == 2
    module1 = course["modules"][0]
    assert module1["slug"] == "foundations"
    assert module1["title"] == "Foundations"

    module2 = course["modules"][1]
    assert module2["slug"] == "modeling"

    # Classes in first module
    classes = module1["classes"]
    assert len(classes) == 3

    assert classes[0]["slug"] == "what-is-a-system"
    assert classes[0]["order"] == 1

    assert classes[1]["slug"] == "feedback-loops"
    assert classes[1]["order"] == 2

    assert classes[2]["slug"] == "video-only-class"
    assert classes[2]["order"] == 3

    # Every class has required fields
    for mod in course["modules"]:
        for cls in mod["classes"]:
            assert "slug" in cls
            assert "title" in cls
            assert "order" in cls


def test_health_still_works(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_media_accept_ranges(client):
    url = "/media/assets/01-intro-to-systems-thinking/01-foundations/01-what-is-a-system/lesson-notes.pdf"
    resp = client.head(url)
    assert resp.status_code == 200
    assert resp.headers.get("accept-ranges") == "bytes"
