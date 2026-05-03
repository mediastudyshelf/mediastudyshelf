# MediaStudyShelf

A local-first learning tool for video, PDF and audio lessons. Point it at a folder of organized media files and get a clean study interface in the browser. No database, no CMS — your folder structure is the content model.

## Quick Start

```bash
docker run -d \
  -p 8000:8000 \
  -v /path/to/your/content:/content:ro \
  -e MEDIASTUDYSHELF_CONTENT_PATH=/content \
  -e SERVE_FRONTEND=1 \
  mediastudyshelf
```

Open [http://localhost:8000](http://localhost:8000).

## Content Structure

Mount a directory with your courses organized as nested folders:

```
/path/to/your/content/
  Spanish for Beginners/
    Module 1 - Basics/
      Lesson 1 - Greetings/
        video.mp4
        lesson.pdf
        walkthrough.mp3
      Lesson 2 - Numbers/
        video.mp4
        worksheet.pdf
    Module 2 - Grammar/
      Lesson 1 - Articles/
        video.mp4
        lesson.pdf
        extra-notes.pdf
        resources.zip
```

Three levels of folders: **Course > Module > Lesson**. Drop media files into lesson folders and they are automatically classified:

| Type | Extensions |
|---|---|
| Video | `.mp4`, `.webm`, `.mov` |
| PDF | `.pdf` |
| Audio | `.mp3`, `.m4a`, `.wav`, `.ogg` |
| Extras | everything else |

### Ordering

Folders and files are sorted using **natural ordering** — numeric values in names are compared numerically, not lexicographically:

- `Lesson 1`, `Lesson 2`, `Lesson 10` sorts as 1, 2, 10
- `01-intro`, `02-grammar` sorts by prefix

You can also use `NN-` prefixes (e.g. `01-greetings`). The prefix is stripped and kebab-case is converted to a display title automatically.

### Multiple Videos and PDFs

When a lesson folder contains multiple videos or PDFs, they are all available through a dropdown selector in the UI. The first file alphabetically (or a well-known name like `lesson.pdf`) is selected by default.

To override the primary PDF, add a `class.json` file:

```json
{
  "primary_pdf": "worksheet.pdf"
}
```

### Optional Metadata

JSON files can be placed at any level to override titles or add metadata:

| File | Location | Fields |
|---|---|---|
| `course.json` | Course folder | `title` |
| `module.json` | Module folder | `title` |
| `class.json` | Lesson folder | `title`, `primary_pdf`, `audio_labels` |

Example `class.json` with audio labels:

```json
{
  "title": "Custom Lesson Title",
  "audio_labels": {
    "q-and-a.mp3": "Q&A Session"
  }
}
```

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `MEDIASTUDYSHELF_CONTENT_PATH` | _(required)_ | Path to the content directory inside the container |
| `SERVE_FRONTEND` | off | Set to `1` to serve the built-in web UI |
| `MEDIASTUDYSHELF_WATCH` | off | Set to `1` to auto-detect content changes (useful during content authoring) |

## Docker Compose

```yaml
services:
  mediastudyshelf:
    image: mediastudyshelf
    ports:
      - "8000:8000"
    volumes:
      - /path/to/your/content:/content:ro
    environment:
      - MEDIASTUDYSHELF_CONTENT_PATH=/content
      - SERVE_FRONTEND=1
    restart: unless-stopped
```

## Features

- **Course browser** — select from all available courses at `/courses`
- **Three-column lesson view** — left nav, video+PDF split, lesson files rail
- **Video player** — native HTML5 with scrubbing support; dropdown selector for multi-video lessons
- **PDF viewer** — page navigation, zoom controls, multi-PDF dropdown selector
- **Audio players** — inline mini-players with progress bars and custom labels
- **Draggable split** — resize the video/PDF division to your preference
- **Smart view switching** — auto-selects PDF-only or video-only mode when content is missing
- **Previous/next navigation** — step through lessons across module boundaries
- **No database** — filesystem is the single source of truth
- **Read-only mount** — your content is mounted as read-only, nothing is modified

## Exposed Port

| Port | Protocol | Description |
|---|---|---|
| 8000 | HTTP | Web UI and API |

## Source Code

[GitHub](https://github.com/mediastudyshelf/mediastudyshelf)

## License

AGPLv3
