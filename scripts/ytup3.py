"""YouTube upload v3 — v1-proven flow + real-mouse final steps + verification.

Usage: python ytup3.py <video.mp4> "<title>"
"""
import sys

from playwright.sync_api import sync_playwright

VIDEO = sys.argv[1]
TITLE = sys.argv[2] if len(sys.argv) > 2 else "Study Companion — demo"
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

    # --- v1-proven entry: studio.youtube.com -> create -> upload
    pg.goto('https://studio.youtube.com', timeout=90000)
    pg.wait_for_timeout(15000)
    log('page:', pg.url[:90])

    pg.evaluate("""() => {
        const b = [...document.querySelectorAll('a, button, ytcp-button')]
            .find(x => /作成|Create/i.test(x.innerText || x.getAttribute('aria-label') || ''));
        if (b) b.click();
    }""")
    pg.wait_for_timeout(4000)
    pg.evaluate("""() => {
        const items = [...document.querySelectorAll('ytcp-button, tp-yt-paper-item, a, li')]
            .filter(x => /アップロード|Upload/i.test(x.innerText || ''));
        if (items.length) items[0].click();
    }""")
    pg.wait_for_timeout(10000)

    fi = None
    for _ in range(30):
        fi = pg.query_selector("input[type=file]")
        if fi:
            break
        pg.wait_for_timeout(1500)
    if not fi:
        log('!! no file input found (dialog never opened)')
        sys.exit(1)
    fi.set_input_files(VIDEO)
    log('file set')
    pg.wait_for_timeout(30000)  # upload + processing + form

    # --- title + desc
    pg.evaluate(
        """([title, desc]) => {
            const boxes = [...document.querySelectorAll('#textbox[contenteditable="true"]')];
            if (boxes[0]) { boxes[0].focus(); document.execCommand('selectAll'); document.execCommand('insertText', false, title); }
            if (boxes[1]) { boxes[1].focus(); document.execCommand('selectAll'); document.execCommand('insertText', false, desc); }
        }""",
        [TITLE, DESCRIPTION],
    )
    log('title+desc set')
    pg.wait_for_timeout(3000)

    # --- next x3 (real mouse on the aria next button)
    for i in range(3):
        pos = pg.evaluate("""() => {
            const b = document.querySelector('#next-button, ytcp-button#next-button');
            if (!b) return null;
            const rc = b.getBoundingClientRect();
            return { x: Math.round(rc.x + rc.width/2), y: Math.round(rc.y + rc.height/2) };
        }""")
        if pos:
            pg.mouse.click(pos['x'], pos['y'])
            log(f'next {i+1} @{pos["x"]},{pos["y"]}')
        else:
            log(f'next {i+1}: button not found')
        pg.wait_for_timeout(6500)

    # --- visibility = unlisted via real mouse + verify
    r = pg.evaluate("""() => {
        const radios = [...document.querySelectorAll('tp-yt-paper-radio-button, ytcp-radio-button')];
        for (const rd of radios) {
            if (/限定公開/.test(rd.innerText || '')) {
                rd.scrollIntoView({ block: 'center' });
                const rc = rd.getBoundingClientRect();
                return { x: Math.round(rc.x + rc.width/2), y: Math.round(rc.y + rc.height/2), checked: rd.getAttribute('aria-checked') };
            }
        }
        return null;
    }""")
    log('unlisted radio:', r)
    if r:
        pg.mouse.click(r['x'], r['y'])
        pg.wait_for_timeout(2500)
        state = pg.evaluate("""() => {
            const radios = [...document.querySelectorAll('tp-yt-paper-radio-button, ytcp-radio-button')];
            for (const rd of radios) {
                if (/限定公開/.test(rd.innerText || '')) return 'aria-checked=' + rd.getAttribute('aria-checked');
            }
            return 'nf';
        }""")
        log('  verified:', state)

    # --- final save/publish (real mouse, prefer 保存 which saves in chosen visibility)
    pos = pg.evaluate("""() => {
        for (const label of ['保存', '公開']) {
            const b = [...document.querySelectorAll('ytcp-button, button')].find(e => (e.innerText || '').trim() === label);
            if (b) {
                b.scrollIntoView({ block: 'center' });
                const rc = b.getBoundingClientRect();
                return { x: Math.round(rc.x + rc.width/2), y: Math.round(rc.y + rc.height/2), label };
            }
        }
        return null;
    }""")
    log('final btn:', pos)
    if pos:
        pg.mouse.click(pos['x'], pos['y'])
        log(f'  clicked {pos["label"]}')
        pg.wait_for_timeout(18000)

    # --- verify via content list
    pg.goto('https://studio.youtube.com/channel/UCIBl4qUGee47H4wx96rswNw/videos/upload', timeout=90000)
    pg.wait_for_timeout(14000)
    rows = pg.evaluate("""() => {
        const out = [];
        document.querySelectorAll('ytcp-video-row').forEach(r => {
            out.push((r.innerText || '').split('\\n').slice(0, 6).join(' / ').slice(0, 130));
        });
        return out.slice(0, 3).join('\\n');
    }""")
    log('ROWS:')
    log(rows)
