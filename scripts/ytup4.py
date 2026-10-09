"""YouTube upload v4 — direct /videos/upload, defensive retries, draft-safe.

Usage: python ytup4.py <video.mp4> "<title>"
"""
import sys

from playwright.sync_api import sync_playwright

VIDEO = sys.argv[1]
TITLE = sys.argv[2] if len(sys.argv) > 2 else "SyllabusSync — demo"
DESCRIPTION = """SyllabusSync — your syllabus, turned into a calendar.
Next Founders Hackathon 2026.

One click extracts every deadline from a syllabus (assignments, quizzes, exams,
project milestones) into an .ics calendar you can import into Google Calendar,
Apple Calendar, or Outlook. Ask anything about the syllabus — late policies,
grading, office hours — and get cited answers, or honest refusals for anything
the syllabus doesn't cover.

Code: https://github.com/maebahesioru/syllabussync"""


def log(*a):
    print(*a, flush=True)


with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp('http://127.0.0.1:9222')
    ctx = browser.contexts[0]
    pg = ctx.new_page()
    pg.on('dialog', lambda d: d.accept())
    pg.bring_to_front()

    pg.goto('https://studio.youtube.com/channel/UCIBl4qUGee47H4wx96rswNw/videos/upload', timeout=90000)
    pg.wait_for_timeout(16000)
    log('page:', pg.url[:100])

    # file input with retries (navigation can destroy context)
    ok = False
    for attempt in range(4):
        try:
            fi = pg.query_selector("input[type=file]")
            if fi:
                fi.set_input_files(VIDEO)
                log('file set')
                ok = True
                break
        except Exception as e:
            log(f'attempt {attempt}: {str(e)[:60]}')
            pg.wait_for_timeout(4000)
    if not ok:
        log('NO FILE INPUT — abort')
        sys.exit(1)

    pg.wait_for_timeout(12000)
    for attempt in range(3):
        try:
            pg.fill('#textbox', TITLE)
            log('title set')
            break
        except Exception as e:
            log(f'title attempt {attempt}: {str(e)[:50]}')
            pg.wait_for_timeout(4000)
    try:
        pg.evaluate("""() => {
            const d = document.querySelector('ytcp-social-suggestions-textbox#description-textarea')
                || document.querySelector('#description-textarea');
            if (!d) return;
            d.focus();
            const ta = d.querySelector('textarea') || d;
            if (ta.tagName === 'TEXTAREA') {
                ta.value = arguments[0] || '';
            }
        }""")
    except Exception:
        pass
    # description via clipboard-less typing into the contenteditable
    try:
        desc_box = pg.query_selector('#description-textarea #textbox') or pg.query_selector('#description-textarea')
        if desc_box:
            desc_box.click()
            pg.keyboard.type(DESCRIPTION, delay=1)
            log('desc set')
    except Exception as e:
        log('desc:', str(e)[:50])
    pg.wait_for_timeout(2000)

    # next x3 with per-step state
    for i in range(3):
        try:
            r = pg.evaluate("""() => {
                const b = document.querySelector('ytcp-uploads-dialog #next-button');
                if (!b) return 'nf';
                b.click(); return 'ok';
            }""")
            log(f'next{i+1}:', r)
        except Exception as e:
            log(f'next{i+1} err: {str(e)[:40]}')
        pg.wait_for_timeout(7000)

    # unlisted if the radio is reachable
    try:
        r = pg.evaluate("""() => {
            const dlg = document.querySelector('ytcp-uploads-dialog');
            if (!dlg) return 'no-dialog';
            for (const rd of dlg.querySelectorAll('tp-yt-paper-radio-button, ytcp-radio-button')) {
                if (/限定公開/.test(rd.innerText || '')) {
                    if (rd.getAttribute('aria-checked') === 'true') return 'already';
                    rd.click(); return 'clicked';
                }
            }
            return 'nf';
        }""")
        log('unlisted:', r)
    except Exception as e:
        log('unlisted err:', str(e)[:40])
    pg.wait_for_timeout(2500)

    # save (draft is fine; publish later via draft editor if needed)
    try:
        r = pg.evaluate("""() => {
            const dlg = document.querySelector('ytcp-uploads-dialog');
            for (const label of ['保存', '公開']) {
                for (const b of dlg.querySelectorAll('ytcp-button, button')) {
                    if ((b.innerText || '').trim() === label) { b.click(); return 'clicked-' + label; }
                }
            }
            return 'nf';
        }""")
        log('save:', r)
    except Exception as e:
        log('save err:', str(e)[:40])
    pg.wait_for_timeout(15000)

    # verify via list
    try:
        pg.goto('https://studio.youtube.com/channel/UCIBl4qUGee47H4wx96rswNw/videos/upload', timeout=90000)
        pg.wait_for_timeout(14000)
        rows = pg.evaluate("""() => {
            const out = [];
            document.querySelectorAll('ytcp-video-row').forEach((r, i) => {
                if (i > 1) return;
                const t = (r.innerText || '').replace(/\\n/g, '|');
                out.push('R' + i + ' TAIL: ' + t.slice(-70));
            });
            return out.join(' // ');
        }""")
        log('ROWS:', rows)
    except Exception as e:
        log('verify err:', str(e)[:60])
