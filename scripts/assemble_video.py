"""Assemble the SyllabusSync demo video (Next Founders edition).

Segments: title card + main recording (app flow + repo walkthrough)
+ business slide still (business narration continues) + end card.
Narration via the app's own TTS endpoint; app answer clips at their marks.
"""
import json
import subprocess
import sys
from pathlib import Path

import urllib.request

ROOT = Path(__file__).parent.parent
DEMO = ROOT / "demo"
FFMPEG = "/home/maebahesioru/.hermes/tools/ffmpeg-9.0.1-linux-x64/bin/ffmpeg"
FFPROBE = "/home/maebahesioru/.hermes/tools/ffmpeg-9.0.1-linux-x64/bin/ffprobe"
FONT = "/usr/share/fonts/noto/NotoSans-Regular.ttf"
API = "http://127.0.0.1:7867"

MAIN_TRIM = 151.0   # seconds of the recording kept (up to business slide)
BIZ_STILL = 50.0    # business slide still duration


def tts(text: str, out: Path) -> None:
    req = urllib.request.Request(
        f"{API}/api/tts",
        data=json.dumps({"text": text}).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=120) as r:
        d = json.load(r)
    url = d["audio_url"]
    with urllib.request.urlopen(f"{API}{url}", timeout=120) as r:
        out.write_bytes(r.read())
    print("tts:", out.name, len(out.read_bytes()) // 1024, "KB")


def dur(p: Path) -> float:
    r = subprocess.run([FFPROBE, "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)],
                       capture_output=True, text=True)
    return float(r.stdout.strip())


def main() -> None:
    marks = {m["name"]: m["t"] for m in json.loads((DEMO / "marks.json").read_text())}
    print("marks:", marks)
    audio_dir = ROOT / "data" / "audio"
    seg_dir = DEMO / "segments"
    seg_dir.mkdir(exist_ok=True)

    # 1) narration segments (start time in final timeline, text)
    segs = [
        (0.5, "SyllabusSync. Your syllabus, turned into a calendar. Every deadline extracted, every policy answerable — with citations, and with honest refusals."),
        (11.0, "Load any syllabus, text or PDF. Every line keeps its exact source."),
        (17.3, "One click, and the AI reads the whole syllabus and pulls out every deadline: assignments, quizzes, exams, project milestones — with their exact dates and times. Here, twenty four deadlines from one syllabus."),
        (30.5, "Every deadline lands in a list — and one click turns them into a calendar file that imports into Google Calendar, Apple Calendar, or Outlook."),
        (55.0, "Ask what's due this week — it knows today's date, so the answer is exact."),
        (88.0, "Ask about the late policy, and every answer cites the section it came from."),
        (105.0, "Ask something the syllabus doesn't cover, and it says so. It never invents deadlines or policies."),
        (124.0, "The build: a FastAPI backend, a retrieval engine over the syllabus, a grounded tutor that cites its sources, and a calendar generator — all open source."),
        (147.5, "The business model: SyllabusSync is free for students. Premium adds auto-sync, reminders, and shared study groups for three ninety nine a month."),
        (172.0, "Campus licenses run a dollar fifty per student per year, and tutoring partners integrate through the API. Extraction costs about two cents per syllabus and is cached forever, so the margin only grows."),
        (194.0, "SyllabusSync. Never miss a deadline again."),
    ]

    narr_files = []
    for i, (start, text) in enumerate(segs):
        f = seg_dir / f"narr_{i:02d}.mp3"
        if not f.exists():
            tts(text, f)
        narr_files.append((start, f))

    # 2) app answer clips (last three mp3s produced during the recording)
    app_clips = []
    if audio_dir.exists():
        files = sorted(audio_dir.glob("*.mp3"), key=lambda p: p.stat().st_mtime)
        if len(files) >= 3:
            app_clips.append((marks.get("ask1", 63) + 0.5, files[-3]))
            app_clips.append((marks.get("ask2", 95) + 0.5, files[-2]))
            app_clips.append((marks.get("refused", 111) + 0.5, files[-1]))

    # 3) mix the audio track
    inputs = []
    filters = []
    idx = 0
    for start, f in narr_files + app_clips:
        inputs += ["-i", str(f)]
        delay = int(start * 1000)
        filters.append(f"[{idx}:a]adelay={delay}|{delay},volume=1.0[a{idx}]")
        idx += 1
    mix_in = "".join(f"[a{i}]" for i in range(idx))
    filters.append(f"{mix_in}amix=inputs={idx}:normalize=0[mix]")
    track = DEMO / "audiotrack.m4a"
    cmd = [FFMPEG, "-y"] + inputs + ["-filter_complex", ";".join(filters), "-map", "[mix]",
                                     "-c:a", "aac", "-b:a", "160k", str(track)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print(r.stderr[-1500:])
        sys.exit(1)
    print("audio track:", dur(track), "s")

    # 4) cards
    title_png = DEMO / "title.png"
    end_png = DEMO / "end.png"
    for png, t1, t2 in [
        (title_png, "SyllabusSync", "your syllabus, turned into a calendar"),
        (end_png, "github.com/maebahesioru/syllabussync", "Never miss a deadline again."),
    ]:
        subprocess.run([FFMPEG, "-y", "-f", "lavfi", "-i", "color=c=0x0b0d12:s=1280x800:d=1", "-frames:v", "1",
                        "-vf", (f"drawtext=fontfile={FONT}:text='{t1}':fontsize=54:fontcolor=white:x=(w-text_w)/2:y=320,"
                                f"drawtext=fontfile={FONT}:text='{t2}':fontsize=28:fontcolor=0x4f8cff:x=(w-text_w)/2:y=420"),
                        str(png)], capture_output=True)

    title_mp4 = DEMO / "title.mp4"
    end_mp4 = DEMO / "end.mp4"
    for png, out, t in [(title_png, title_mp4, "5"), (end_png, end_mp4, "6")]:
        subprocess.run([FFMPEG, "-y", "-loop", "1", "-i", str(png), "-t", t, "-r", "30",
                        "-c:v", "libx264", "-pix_fmt", "yuv420p", str(out)], capture_output=True)

    # 5) main video: trim recording, add the (trimmed) audio track
    raw = next(DEMO.glob("video/*.webm"))
    track_trim = DEMO / "audiotrack_trim.m4a"
    subprocess.run([FFMPEG, "-y", "-i", str(track), "-t", str(MAIN_TRIM + 0.5), "-c:a", "copy", str(track_trim)],
                   capture_output=True)
    main_mp4 = DEMO / "demo_main.mp4"
    subprocess.run([FFMPEG, "-y", "-i", str(raw), "-i", str(track_trim),
                    "-map", "0:v", "-map", "1:a", "-t", str(MAIN_TRIM),
                    "-c:v", "libx264", "-preset", "fast", "-crf", "23",
                    "-pix_fmt", "yuv420p", "-c:a", "aac", str(main_mp4)], capture_output=True)
    print("main:", dur(main_mp4), "s")

    # 6) business still with continuing narration
    biz_png = DEMO / "business.png"
    biz_mp4 = DEMO / "business_seg.mp4"
    subprocess.run([FFMPEG, "-y", "-loop", "1", "-i", str(biz_png), "-t", str(BIZ_STILL), "-r", "30",
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", str(biz_mp4)], capture_output=True)
    # business audio slice from the full track
    biz_track = DEMO / "biz_track.m4a"
    subprocess.run([FFMPEG, "-y", "-ss", str(MAIN_TRIM), "-i", str(track), "-t", str(BIZ_STILL),
                    "-c:a", "aac", str(biz_track)], capture_output=True)
    biz_a = DEMO / "business_seg_a.mp4"
    subprocess.run([FFMPEG, "-y", "-i", str(biz_mp4), "-i", str(biz_track), "-map", "0:v", "-map", "1:a",
                    "-c:v", "copy", "-c:a", "aac", "-shortest", str(biz_a)], capture_output=True)

    # 7) silent audio for the cards + concat everything
    silent1 = DEMO / "silence5.m4a"
    silent2 = DEMO / "silence6.m4a"
    for out, t in [(silent1, "5"), (silent2, "6")]:
        subprocess.run([FFMPEG, "-y", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo", "-t", t,
                        "-c:a", "aac", str(out)], capture_output=True)
    t2 = DEMO / "title_a.mp4"
    e2 = DEMO / "end_a.mp4"
    subprocess.run([FFMPEG, "-y", "-i", str(title_mp4), "-i", str(silent1), "-map", "0:v", "-map", "1:a",
                    "-c:v", "copy", "-c:a", "aac", "-shortest", str(t2)], capture_output=True)
    subprocess.run([FFMPEG, "-y", "-i", str(end_mp4), "-i", str(silent2), "-map", "0:v", "-map", "1:a",
                    "-c:v", "copy", "-c:a", "aac", "-shortest", str(e2)], capture_output=True)

    concat = DEMO / "concat.txt"
    concat.write_text(f"file '{t2}'\nfile '{main_mp4}'\nfile '{biz_a}'\nfile '{e2}'\n")
    final = DEMO / "syllabussync_demo.mp4"
    subprocess.run([FFMPEG, "-y", "-f", "concat", "-safe", "0", "-i", str(concat), "-c", "copy", str(final)],
                   capture_output=True)
    print("FINAL:", final, dur(final), "s")


if __name__ == "__main__":
    main()
