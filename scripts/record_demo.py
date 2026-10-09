"""Record the SyllabusSync demo — upload -> extract deadlines -> Q&A -> refusal
-> repo walkthrough -> business slide.

Prereq: server on :7867 (deadline cache warm), CDP browser on :9222.
Produces: demo/video/*.webm + demo/marks.json
"""
import json
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

OUT = Path(__file__).parent.parent / "demo"
OUT.mkdir(exist_ok=True)
VID = OUT / "video"
VID.mkdir(exist_ok=True)
APP = "http://127.0.0.1:7867"
REPO = "https://github.com/maebahesioru/syllabussync"
BUSINESS = "file://" + str(Path(__file__).parent.parent / "docs" / "business.html")
marks: list[dict] = []
t0 = time.time()


def mark(name: str) -> None:
    marks.append({"name": name, "t": round(time.time() - t0, 2)})
    print(f"MARK {name} @ {marks[-1]['t']}s", flush=True)


def slow(page, ms=600):
    page.wait_for_timeout(ms)


def wait_answer(page, timeout=90000):
    page.wait_for_function(
        "() => { const b = document.querySelectorAll('#chat .msg.bot');"
        " if (!b.length) return false;"
        " return !b[b.length-1].querySelector('.spin'); }",
        timeout=timeout,
    )


with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    ctx = browser.new_context(
        viewport={"width": 1280, "height": 800},
        record_video_dir=str(VID),
        record_video_size={"width": 1280, "height": 800},
    )
    page = ctx.new_page()
    page.on("dialog", lambda d: d.accept())

    page.goto(APP, timeout=60000)
    slow(page, 3500)
    mark("start")

    # upload the syllabus
    page.set_input_files("#file", [str(OUT.parent / "data/sample_course/syllabus_cs101.md")])
    slow(page, 6500)
    mark("uploaded")

    # extract deadlines
    page.click("nav button[data-t='timeline']")
    slow(page, 1500)
    page.click("#btnTimeline")
    slow(page, 5000)
    mark("extracted")
    page.evaluate("window.scrollTo(0, 300)")
    slow(page, 3500)
    page.evaluate("window.scrollTo(0, 700)")
    slow(page, 3500)
    page.evaluate("window.scrollTo(0, 1100)")
    slow(page, 3000)

    # Q1: due this week
    page.click("nav button[data-t='tutor']")
    slow(page, 1200)
    page.fill("#q", "What is due this week?")
    slow(page, 800)
    page.click("#btnAsk")
    slow(page, 3000)
    wait_answer(page)
    mark("ask1")
    slow(page, 6000)
    page.evaluate("window.scrollTo(0, 500)")
    slow(page, 4000)

    # Q2: late policy
    page.evaluate("window.scrollTo(0, 0)")
    page.fill("#q", "What is the late policy for assignments?")
    slow(page, 800)
    page.click("#btnAsk")
    slow(page, 3000)
    wait_answer(page)
    mark("ask2")
    slow(page, 5000)
    page.evaluate("window.scrollTo(0, 400)")
    slow(page, 4000)

    # refusal
    page.evaluate("window.scrollTo(0, 0)")
    page.fill("#q", "What is the Wi-Fi password for the classroom?")
    slow(page, 800)
    page.click("#btnAsk")
    slow(page, 3000)
    wait_answer(page)
    mark("refused")
    slow(page, 6000)

    # repo walkthrough
    page.goto(REPO, timeout=60000)
    slow(page, 4000)
    mark("repo")
    page.evaluate("window.scrollTo(0, 500)")
    slow(page, 4000)
    page.evaluate("window.scrollTo(0, 1100)")
    slow(page, 4000)
    page.evaluate("window.scrollTo(0, 1800)")
    slow(page, 4000)
    page.evaluate("window.scrollTo(0, 2400)")
    slow(page, 3500)

    # business slide
    page.goto(BUSINESS, timeout=30000)
    slow(page, 5000)
    mark("business")
    slow(page, 14000)

    mark("end")
    ctx.close()

    marks_path = OUT / "marks.json"
    marks_path.write_text(json.dumps(marks, indent=1))
    vids = list(VID.glob("*.webm"))
    print("VIDEO:", vids[-1] if vids else "NONE")
    print("marks saved")
