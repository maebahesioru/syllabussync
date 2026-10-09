"""Syllabus intelligence — extract every deadline and turn it into a calendar.

SyllabusSync's core value: a syllabus is a wall of text; students need a calendar.
 1. extract_deadlines(): LLM reads the syllabus and returns structured deadlines
    (title, date, time, kind, source line).
 2. to_ics(): the deadlines become a standard .ics calendar file any calendar app
    can import — the moment a student loads their syllabus.
"""
from __future__ import annotations

import datetime as _dt
import json
import re
from pathlib import Path

from .ingest import KnowledgeBase
from . import llm

DATA = Path(__file__).parent.parent / "data"
CACHE = DATA / "deadlines.json"

EXTRACT_SYSTEM = """You extract every graded deadline from a course syllabus.

Return JSON:
{
 "deadlines": [
   {
     "title": "Assignment 1: Hello, Python",
     "date": "2026-09-18",
     "time": "23:59",
     "kind": "assignment" | "quiz" | "exam" | "project" | "other",
     "details": "one short sentence (from the syllabus)",
     "source_unit_id": "unit id containing this line"
   }
 ]
}
Rules:
- Include EVERY deadline with an explicit date: assignments, quizzes, exams, project
  milestones, and demos. Do not invent dates.
- Use ISO dates (YYYY-MM-DD). If a time is given use HH:MM (24h); otherwise "".
- Quizzes in class: use the class time if stated, otherwise "".
- Keep titles close to the syllabus wording.
"""


def _clean_json(text: str) -> dict:
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text
        if text.endswith("```"):
            text = text[:-3]
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        s = min((text.find(c) for c in "{[" if text.find(c) != -1), default=-1)
        e = max(text.rfind("}"), text.rfind("]"))
        if s != -1 and e > s:
            return json.loads(text[s : e + 1])
        raise


def extract_deadlines(kb: KnowledgeBase, force: bool = False) -> list[dict]:
    """LLM-extract deadlines from the syllabus; cached to data/deadlines.json."""
    if CACHE.exists() and not force:
        try:
            return json.loads(CACHE.read_text(encoding="utf-8")).get("deadlines", [])
        except Exception:
            pass
    if not kb.units:
        return []
    # the schedule section carries the dates; send the most date-rich units first
    dated = sorted(kb.units, key=lambda u: -len(re.findall(r"20\d\d", u.text)))
    listing = "\n\n".join(f"[{u.id}] {u.text[:1500]}" for u in dated[:6])
    out = llm.chat_json(
        [{"role": "system", "content": EXTRACT_SYSTEM},
         {"role": "user", "content": listing}],
        max_tokens=4000,
    )
    deadlines = out.get("deadlines", []) if isinstance(out, dict) else []
    # validate
    clean = []
    for d in deadlines:
        date = str(d.get("date", "")).strip()
        if not re.fullmatch(r"20\d\d-\d\d-\d\d", date):
            continue
        d["title"] = str(d.get("title", "Untitled"))[:120]
        d["time"] = str(d.get("time", "") or "")
        d["kind"] = str(d.get("kind", "other"))
        d["details"] = str(d.get("details", ""))[:200]
        clean.append(d)
    clean.sort(key=lambda d: (d["date"], d["time"]))
    CACHE.parent.mkdir(exist_ok=True)
    CACHE.write_text(json.dumps({"deadlines": clean}, ensure_ascii=False, indent=1), encoding="utf-8")
    return clean


def upcoming(deadlines: list[dict], within_days: int = 14) -> list[dict]:
    today = _dt.date.today()
    end = today + _dt.timedelta(days=within_days)
    out = []
    for d in deadlines:
        try:
            dt = _dt.date.fromisoformat(d["date"])
        except ValueError:
            continue
        if today <= dt <= end:
            out.append(d)
    return out


def to_ics(deadlines: list[dict], calendar_name: str = "SyllabusSync") -> str:
    """Generate an .ics calendar (all deadlines as timed events or all-day)."""
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//SyllabusSync//EN",
        f"X-WR-CALNAME:{calendar_name}",
    ]
    stamp = _dt.datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    for i, d in enumerate(deadlines):
        try:
            date = _dt.date.fromisoformat(d["date"])
        except ValueError:
            continue
        t = (d.get("time") or "").strip()
        summary = d["title"].replace(",", "\\,")
        desc = (d.get("details") or "").replace(",", "\\,")
        lines.append("BEGIN:VEVENT")
        lines.append(f"UID:syllabussync-{i}@localhost")
        lines.append(f"DTSTAMP:{stamp}")
        if re.fullmatch(r"\d{1,2}:\d{2}", t):
            hh, mm = t.split(":")
            start = _dt.datetime.combine(date, _dt.time(int(hh), int(mm)))
            end = start + _dt.timedelta(minutes=30)
            lines.append(f"DTSTART:{start.strftime('%Y%m%dT%H%M%S')}")
            lines.append(f"DTEND:{end.strftime('%Y%m%dT%H%M%S')}")
        else:
            lines.append(f"DTSTART;VALUE=DATE:{date.strftime('%Y%m%d')}")
        lines.append(f"SUMMARY:{summary} ({d.get('kind', 'other')})")
        if desc:
            lines.append(f"DESCRIPTION:{desc}")
        lines.append("END:VEVENT")
    lines.append("END:VCALENDAR")
    return "\r\n".join(lines)
