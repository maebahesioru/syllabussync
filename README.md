# SyllabusSync

**Your syllabus, turned into a calendar — and every answer about it, cited.**

SyllabusSync reads a course syllabus (PDF or text) and does two things no LMS does well:

1. **Extracts every deadline** — assignments, quizzes, exams, project milestones — with
   dates and times, and turns them into a `.ics` calendar file you can import into
   Google Calendar, Apple Calendar, or Outlook.
2. **Answers any question about the syllabus** — late policies, grading, office hours,
   exam coverage — with citations to the exact section, and refuses to invent anything
   the syllabus doesn't say.

Built for the Next Founders Hackathon 2026.

## Quick start

```bash
cd syllabussync
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp config.example.env .env        # fill in your LLM endpoint + key
python -m uvicorn server:app --host 127.0.0.1 --port 7867
```

Open http://127.0.0.1:7867 — a sample syllabus ships in `data/sample_course/`.

### Configure (.env)

```
LLM_BASE_URL=https://opencode.ai/zen/go/v1
LLM_API_KEY=<your key>
LLM_MODEL=deepseek-v4.1-flash
LLM_EXTRA_HEADERS={"x-opencode-session": "syllabussync-ses-001"}
```

Any OpenAI-compatible endpoint works (OpenAI, OpenRouter, a local model, etc.).
The `x-opencode-session` header is only needed for OpenCode Go.

## How it works

```
syllabus (md/pdf/txt)
   │  core/ingest.py       — parses text into source-tagged units
   ▼
knowledge base (data/kb.json)
   │  core/syllabus.py     — LLM extracts every dated deadline → data/deadlines.json
   │                        — generates .ics (VEVENT per deadline)
   │  core/retriever.py    — TF-IDF retrieval over the units
   │  core/tutor.py        — grounded answer + citations, or honest refusal
   ▼
FastAPI server (server.py) — /api/upload /api/deadlines /api/ics /api/chat /api/tts
   ▼
static/index.html — single-page UI: Load · Ask · Deadlines
```

- **Deadline extraction** (`core/syllabus.py:extract_deadlines`): sends the date-rich
  units to the LLM with a strict JSON schema, validates every date, sorts, caches.
- **Calendar export** (`core/syllabus.py:to_ics`): RFC 5545 VCALENDAR with one VEVENT
  per deadline (timed when the syllabus gives a time).
- **Schedule-aware answers** (`server.py:/api/chat`): "what's due this week" gets
  today's date + the extracted deadline list injected, so the answer is exact.
- **Grounded tutor** (`core/tutor.py`): every claim cites a unit id; off-syllabus
  questions return a labeled refusal instead of a guess.

## API reference

| Endpoint | Method | What it does |
|---|---|---|
| `/api/upload` | POST (multipart) | Add a syllabus file to the knowledge base |
| `/api/deadlines` | GET | Extract (or return cached) all deadlines |
| `/api/ics` | GET | Download the deadlines as a calendar file |
| `/api/chat` | POST `{"question": "..."}` | Cited answer or refusal (+audio URL) |
| `/api/tts` | POST `{"text": "..."}` | Text-to-speech (Edge TTS) |

## Honest limits

- Deadline extraction is one LLM call per syllabus; a 30-page syllabus can take
  ~60 seconds. Results are cached in `data/deadlines.json` after the first run.
- The calendar export uses floating local times (no timezone conversion).
- Retrieval is TF-IDF — great for one syllabus, not built for cross-course search yet.
