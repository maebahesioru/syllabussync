"""Grounded tutor — answers strictly from retrieved course excerpts, with citations.

Design:
  - The tutor sees ONLY the top retrieved excerpts.
  - It must cite each claim with [unit_id] markers.
  - If the excerpts don't cover the question it must refuse and say so
    (the API layer also returns the refusal flag for the UI).
  - Outside knowledge is never blended silently: a clearly separated
    "Not in your materials" note is allowed only when the person asked
    something the material misses, and it is flagged.
"""
from __future__ import annotations

from .ingest import Unit
from .retrieve import Retriever
from . import llm

TUTOR_SYSTEM = """You are SyllabusSync, a student's syllabus assistant. You answer questions using ONLY the provided excerpts from the student's syllabus.

Rules (strict):
1. Answer ONLY using the provided excerpts. Never invent deadlines, dates, policies, or grading rules.
2. Cite every fact with the excerpt id in square brackets, e.g. [u1a2b3c4], and name the section (e.g. "Late Policy", "Schedule").
3. For deadline questions, give the exact date and time from the syllabus, and the item name.
4. If the syllabus does not cover the question, reply exactly:
   "NOT_COVERED: I couldn't find this in the syllabus."
   followed by one short sentence about what IS covered nearby (if anything).
5. Be clear and practical: students are planning their week. Short lists beat paragraphs.
6. When asked about anything requiring a decision (extensions, emergencies), point to the instructor's stated process.
"""






def answer(question: str, retriever: Retriever, k: int = 6, rerank: bool = True) -> dict:
    hits = retriever.search(question, k=k)
    if rerank:
        hits = retriever.rerank(question, hits, top=4)
    else:
        hits = hits[:4]

    if not hits:
        return {
            "answer": "NOT_COVERED: I couldn't find this in the syllabus.",
            "citations": [],
            "refused": True,
        }

    context = "\n\n".join(
        f"[{u.id}] (source: {u.source_file}, {u.location})\n{u.text}" for u, _s in hits
    )
    user = (
        f"Student question: {question}\n\n"
        f"Available excerpts:\n{context}\n\n"
        "Answer with citations, or refuse with NOT_COVERED if not covered."
    )
    text = llm.chat(
        [{"role": "system", "content": TUTOR_SYSTEM}, {"role": "user", "content": user}],
        temperature=0.15,
        max_tokens=900,
    )

    refused = text.strip().startswith("NOT_COVERED")
    citations = []
    for u, score in hits:
        if u.id in text:
            citations.append(
                {
                    "unit_id": u.id,
                    "source_file": u.source_file,
                    "location": u.location,
                    "source_type": u.source_type,
                    "excerpt": u.text[:300],
                    "score": round(score, 3),
                }
            )
    return {"answer": text.strip(), "citations": citations, "refused": refused}
