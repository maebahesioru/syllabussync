"""Timeline — turn multiple dated documents into a chronological health story.

Caregivers juggle reports from different dates and providers. This module:
 1. extracts dated events (report date + each test row) from source-linked units,
 2. builds a chronological timeline across all documents,
 3. detects trends for repeated measurements (e.g. HbA1c rising over visits),
 4. generates caregiver-facing questions for the next appointment.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, asdict

from .ingest import KnowledgeBase, Unit

DATE_RE = re.compile(
    r"(20\d{2})[-/年](\d{1,2})[-/月](\d{1,2})?日?"
)
# test row: "Ferritin | 9 ng/mL | 30 – 300 ng/mL | LOW"
ROW_RE = re.compile(
    r"^\|?\s*([A-Za-z][A-Za-z0-9 ()\-/]{2,40}?)\s*\|\s*([\d.]+)\s*([a-zA-Z%/×^0-9.\-]*)\s*\|\s*([^|]{2,40})\|\s*(LOW|HIGH|normal|low|high)?",
    re.M,
)


@dataclass
class Event:
    date: str
    kind: str  # "report" | "measurement"
    label: str
    value: str = ""
    reference: str = ""
    flag: str = ""
    source_file: str = ""
    location: str = ""
    unit_id: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


def _norm_date(m: re.Match) -> str:
    y, mo, d = m.group(1), int(m.group(2)), m.group(3)
    return f"{y}-{mo:02d}" + (f"-{int(d):02d}" if d else "")


def extract_events(kb: KnowledgeBase) -> list[Event]:
    events: list[Event] = []
    for u in kb.units:
        # report-level date (first date found in the unit)
        dates = [_norm_date(m) for m in DATE_RE.finditer(u.text)]
        report_date = dates[0] if dates else ""
        if report_date:
            title = u.text.split("\n", 1)[0].lstrip("# ").strip()[:70]
            events.append(
                Event(date=report_date, kind="report", label=title or u.source_file,
                      source_file=u.source_file, location=u.location, unit_id=u.id)
            )
        # measurement rows
        for m in ROW_RE.finditer(u.text):
            name = m.group(1).strip()
            if name.lower() in ("test", "result", "value"):
                continue
            val = f"{m.group(2)} {m.group(3)}".strip()
            events.append(
                Event(
                    date=report_date or "undated",
                    kind="measurement",
                    label=name,
                    value=val,
                    reference=(m.group(4) or "").strip(),
                    flag=(m.group(5) or "").strip().upper(),
                    source_file=u.source_file,
                    location=u.location,
                    unit_id=u.id,
                )
            )
    events.sort(key=lambda e: (e.date or "9999", e.kind))
    return events


def _num(v: str) -> float | None:
    m = re.search(r"([\d.]+)", v or "")
    return float(m.group(1)) if m else None


def detect_trends(events: list[Event]) -> list[dict]:
    """Group measurements by name; report changes across dates."""
    by_name: dict[str, list[Event]] = {}
    for e in events:
        if e.kind == "measurement" and e.date != "undated":
            by_name.setdefault(e.label.lower(), []).append(e)
    trends = []
    for name, items in by_name.items():
        if len(items) < 2:
            continue
        items.sort(key=lambda e: e.date)
        first, last = items[0], items[-1]
        v1, v2 = _num(first.value), _num(last.value)
        if v1 is None or v2 is None:
            continue
        direction = "rising" if v2 > v1 else ("falling" if v2 < v1 else "stable")
        trends.append(
            {
                "measurement": first.label,
                "first": {"date": first.date, "value": first.value, "flag": first.flag},
                "latest": {"date": last.date, "value": last.value, "flag": last.flag},
                "direction": direction,
                "delta": round(v2 - v1, 2),
                "n": len(items),
                "source_unit": last.unit_id,
            }
        )
    trends.sort(key=lambda t: -abs(t["delta"]))
    return trends


QUESTION_TEMPLATES = {
    "rising": "The {m} has risen from {v1} ({d1}) to {v2} ({d2}) — what could explain this, and should we investigate?",
    "falling": "The {m} has fallen from {v1} ({d1}) to {v2} ({d2}) — is this expected with the current plan?",
    "stable": "The {m} has stayed around {v2} since {d1} — is the current management working?",
}


def caregiver_questions(trends: list[dict], flagged: list[Event], limit: int = 6) -> list[str]:
    qs: list[str] = []
    for t in trends[:4]:
        tmpl = QUESTION_TEMPLATES.get(t["direction"])
        if tmpl:
            qs.append(tmpl.format(
                m=t["measurement"], v1=t["first"]["value"], d1=t["first"]["date"],
                v2=t["latest"]["value"], d2=t["latest"]["date"],
            ))
    for e in flagged[:3]:
        if e.flag in ("LOW", "HIGH"):
            qs.append(f"The {e.label} was flagged {e.flag} ({e.value}) on {e.date} — what does it mean and what should we do?")
    return qs[:limit]


def build_timeline(kb: KnowledgeBase) -> dict:
    events = extract_events(kb)
    trends = detect_trends(events)
    flagged = [e for e in events if e.flag in ("LOW", "HIGH")]
    return {
        "events": [e.to_dict() for e in events],
        "reports": [e.to_dict() for e in events if e.kind == "report"],
        "trends": trends,
        "flagged": [e.to_dict() for e in flagged],
        "questions": caregiver_questions(trends, flagged),
        "summary": {
            "reports": sum(1 for e in events if e.kind == "report"),
            "measurements": sum(1 for e in events if e.kind == "measurement"),
            "trends": len(trends),
            "flagged": len(flagged),
        },
    }
