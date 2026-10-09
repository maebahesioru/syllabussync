SyllabusSync turns a course syllabus into a calendar and answers every question about it — with citations.

**The problem.** Every semester, students get a wall of text called a syllabus. Deadlines hide in paragraphs, policies are scattered, and every LMS shows them in a different place. Students miss things not because they don't care, but because a syllabus is not a calendar.

**What SyllabusSync does.**
- Load any syllabus (text or PDF). Every line keeps its exact source.
- One click extracts every deadline: assignments, quizzes, exams, project milestones — with dates and times — into a list.
- One more click turns them into an .ics calendar file that imports into Google Calendar, Apple Calendar, or Outlook.
- Ask anything: "What's due this week?" (it knows today's date), "What's the late policy?", "How is the final project graded?" Every answer cites the exact section it came from.
- Anything the syllabus doesn't cover gets an honest refusal — never an invented deadline.

**Technical execution.** A FastAPI backend serves a single-page app. The pipeline: syllabus parsing into source-tagged units, TF-IDF retrieval, an LLM tutor with a strict cite-or-refuse contract, and a deadline extractor that validates every date before it reaches the calendar. Schedule questions get today's date plus the extracted deadline list injected, so "due this week" is exact. Calendar export is plain RFC 5545 — no lock-in. The demo video shows the full flow on a real 30-page syllabus: 24 deadlines extracted, a week-view answer, a policy answer, and a refusal.

**Innovation & UX.** Most "AI for students" tools are chat wrappers. SyllabusSync makes the syllabus machine-readable in two directions: text → calendar, and text → cited answers. The refusal behavior is the trust feature — a student can act on a deadline without double-checking the syllabus.

**Business model.** Free for students: extraction, calendar export, 20 questions/month. Student Premium ($3.99/mo or $24/yr): unlimited questions, auto-sync, weekly deadline digest, shared study-group calendars. Campus licenses at $1.50/student/year for universities (orientation handouts, advising offices). Tutoring platforms and LMS integrations via API. Unit economics: extraction is one LLM call per syllabus (~$0.02, cached forever); hosting runs ~$20/month for thousands of students. A 3–5% premium conversion covers costs at ~1,500 active students.

**Built with:** Python, FastAPI, scikit-learn (TF-IDF retrieval), Edge TTS, vanilla JS single-page UI. Code: https://github.com/maebahesioru/syllabussync
