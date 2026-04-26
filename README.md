# MediaStudyShelf

A local-first learning tool for video, PDF and audio lessons. Your folder structure is the content model, no CMS, no imports.

![Lesson view](images/lesson-page.svg)

## Quick Start with Docker

The easiest way to run MediaStudyShelf is with the pre-built image from [Docker Hub](https://hub.docker.com/r/mediastudyshelf/mediastudyshelf).

### Using Docker Compose

Create a `docker-compose.yaml`:

```yaml
services:
  mediastudyshelf:
    image: mediastudyshelf/mediastudyshelf
    ports:
      - "8000:8000"
    volumes:
      - /path/to/your/content:/content:ro
    environment:
      - MEDIASTUDYSHELF_CONTENT_PATH=/content
      - SERVE_FRONTEND=1
    restart: unless-stopped
```

```bash
docker compose up -d
```

Open http://localhost:8000.

### Using Docker directly

```bash
docker run -d \
  -p 8000:8000 \
  -v /path/to/your/content:/content:ro \
  -e MEDIASTUDYSHELF_CONTENT_PATH=/content \
  -e SERVE_FRONTEND=1 \
  mediastudyshelf/mediastudyshelf
```

Replace `/path/to/your/content` with the path to your course folders.

---

## Development

### With Docker (recommended)

```bash
make up     # starts backend + frontend with hot reload
make down   # stops and removes containers
```

Open http://localhost:5173.

### Bare-metal

```bash
# Terminal 1: Python backend (requires Python 3.11+, ffmpeg)
pip install -e ".[dev]"
MEDIASTUDYSHELF_WATCH=1 uvicorn mediastudyshelf.main:app --reload

# Terminal 2: Vite dev server (requires Node.js 20+)
cd client && npm install && npm run dev
```

Open http://localhost:5173.

### Production build

```bash
# Build the Docker image
make build

# Or build manually without Docker
cd client && npm run build && cd ..
SERVE_FRONTEND=1 uvicorn mediastudyshelf.main:app --host 0.0.0.0 --port 8000
```

## Environment variables

| Variable | Default | Description |
|---|---|---|
| `MEDIASTUDYSHELF_CONTENT_PATH` | `./sample-content` | Path to the content directory |
| `MEDIASTUDYSHELF_WATCH` | off | Set to `1` to re-walk content on filesystem changes (dev mode) |
| `SERVE_FRONTEND` | off | Set to `1` to serve the built frontend from `/client/dist` |

## Content structure

```
/content
  /Course Name/
    course.json                    (optional — override title)
    /Module Name/
      module.json                  (optional — override title)
      /Class Name/
        class.json                 (optional — override title, audio labels, primary PDF)
        video.mp4                  (primary video — first alphabetically)
        lesson.pdf                 (primary PDF — or main.pdf, or first alphabetically)
        worksheet.pdf              (additional PDF)
        walkthrough.mp3            (audio)
        resources.zip              (extras — anything not video/pdf/audio)
```

### Ordering

Folders are sorted using **natural ordering**, so numeric values in names are compared numerically rather than lexicographically. This means you can name your folders however you like and they will sort intuitively:

| Naming style | Sort result |
|---|---|
| `Aula 1`, `Aula 2`, `Aula 10` | 1 → 2 → 10 |
| `01-foundations`, `02-modeling` | 01 → 02 |
| `Módulo 1`, `Módulo 2`, `Módulo 10` | 1 → 2 → 10 |

Folders with an `NN-` prefix (e.g. `01-intro`) have their prefix stripped for display (kebab-case → sentence case). Folders without a prefix are displayed as-is.

### File classification

| Type | Extensions |
|---|---|
| Video | `.mp4`, `.webm`, `.mov` |
| PDF | `.pdf` |
| Audio | `.mp3`, `.m4a`, `.wav`, `.ogg` |
| Extras | everything else |

### Primary PDF resolution

1. `class.json` → `"primary_pdf": "filename.pdf"`
2. A file named `lesson.pdf` or `main.pdf`
3. First PDF alphabetically

## Tests

```bash
pytest
```
