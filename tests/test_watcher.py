"""Integration test for the filesystem watcher."""

import os
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pypdf import PdfWriter


@pytest.fixture
def watched_app(tmp_path):
    """Create a minimal content tree in a temp dir, start app with watcher enabled."""
    # Build a tiny content tree
    course = tmp_path / "01-test-course" / "01-intro" / "01-first-class"
    course.mkdir(parents=True)
    pdf = course / "lesson.pdf"
    w = PdfWriter()
    w.add_blank_page(612, 792)
    with open(pdf, "wb") as f:
        w.write(f)

    os.environ["MEDIASTUDYSHELF_CONTENT_PATH"] = str(tmp_path)
    os.environ["MEDIASTUDYSHELF_WATCH"] = "1"

    # Force reimport so lifespan picks up the new env vars
    import importlib
    import mediastudyshelf.main
    importlib.reload(mediastudyshelf.main)

    try:
        with TestClient(mediastudyshelf.main.app) as client:
            yield client, tmp_path
    finally:
        os.environ.pop("MEDIASTUDYSHELF_WATCH", None)
        os.environ.pop("MEDIASTUDYSHELF_CONTENT_PATH", None)


@pytest.mark.slow
def test_watcher_detects_new_class(watched_app):
    client, content_dir = watched_app

    # Baseline: one class
    resp = client.get("/api/tree")
    assert resp.status_code == 200
    classes = resp.json()["courses"][0]["modules"][0]["classes"]
    assert len(classes) == 1

    # Add a new class folder with a file
    new_class = content_dir / "01-test-course" / "01-intro" / "02-second-class"
    new_class.mkdir()
    (new_class / "notes.txt").write_text("hello")

    # Wait for debounce + re-walk (watcher debounce is 500ms)
    time.sleep(2)

    # Tree should now include the new class
    resp = client.get("/api/tree")
    classes = resp.json()["courses"][0]["modules"][0]["classes"]
    assert len(classes) == 2
    slugs = [c["slug"] for c in classes]
    assert "second-class" in slugs
