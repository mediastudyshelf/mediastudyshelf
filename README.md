# MediaStudyShelf

A local-first learning tool for video, PDF and audio lessons. Your folder structure is the content model, no CMS, no imports.

## Prerequisites

- Python 3.11+
- Node.js 20.19+
- ffmpeg (provides `ffprobe` for media duration extraction)

## Setup

```bash
# Install Python package (editable, with dev dependencies)
pip install -e ".[dev]"

# Install frontend dependencies
cd client && npm install && cd ..
```

## Development

Run two processes in separate terminals:

```bash
# Terminal 1: Python backend
MEDIASTUDYSHELF_WATCH=1 uvicorn mediastudyshelf.main:app --reload

# Terminal 2: Vite dev server (proxies /api and /media to :8000)
cd client && npm run dev
```

Open the Vite URL (typically http://localhost:5173).

## Production

```bash
# Build the frontend
cd client && npm run build && cd ..

# Run everything from one server
SERVE_FRONTEND=1 uvicorn mediastudyshelf.main:app --host 0.0.0.0 --port 8000
```

Open http://localhost:8000.

## Environment variables

| Variable | Default | Description |
|---|---|---|
| `MEDIASTUDYSHELF_CONTENT_PATH` | `./sample-content` | Path to the content directory |
| `MEDIASTUDYSHELF_WATCH` | off | Set to `1` to re-walk content on filesystem changes (dev mode) |
| `SERVE_FRONTEND` | off | Set to `1` to serve the built frontend from `/client/dist` |

## Content structure

```
/content
  /01-course-name/
    course.json              (optional)
    /01-module-name/
      /01-class-name/
        video.mp4
        lesson-notes.pdf
        walkthrough.mp3
```

Folders prefixed with `NN-` are ordered by that number. Display names are derived from the slug (kebab-case → sentence case). See `docs/SPEC.md` for the full content model.

## Tests

```bash
pytest
```
