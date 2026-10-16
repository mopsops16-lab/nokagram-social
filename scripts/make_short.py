#!/usr/bin/env python3
"""Render a vertical promo short for the NokaGram Telegram channel.

Pipeline:
  script (topics.json) -> edge-tts voice-over -> ASS captions from word
  boundaries -> procedural ffmpeg background + branding -> out/<id>.mp4 + meta.

No API keys required to render. Publishing is done by a separate script.
"""

import argparse
import asyncio
import datetime as dt
import json
import os
import shutil
import subprocess
import sys
import tempfile

import edge_tts

W, H, FPS = 1080, 1920, 30
HANDLE = "@NokaGram"


def run(cmd, **kw):
    print("+", " ".join(str(c) for c in cmd), flush=True)
    subprocess.run(cmd, check=True, **kw)


def ffprobe_duration(path):
    out = subprocess.check_output(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "csv=p=0", path],
        text=True,
    ).strip()
    return float(out)


def pick_topic(topics, forced=None):
    if forced:
        for t in topics:
            if t["id"] == forced:
                return t
        raise SystemExit(f"topic id not found: {forced}")
    doy = dt.date.today().timetuple().tm_yday
    return topics[doy % len(topics)]


async def synth(text, voice, out_mp3):
    """Render speech and return word boundaries [(start_s, end_s, word)]."""
    comm = edge_tts.Communicate(text, voice)
    words = []
    with open(out_mp3, "wb") as f:
        async for chunk in comm.stream():
            if chunk["type"] == "audio":
                f.write(chunk["data"])
            elif chunk["type"] == "WordBoundary":
                start = chunk["offset"] / 1e7
                end = (chunk["offset"] + chunk["duration"]) / 1e7
                words.append((start, end, chunk["text"]))
    if not words:
        raise SystemExit("edge-tts returned no word boundaries")
    return words


def ass_ts(seconds):
    seconds = max(0.0, seconds)
    cs = int(round(seconds * 100))
    h, rem = divmod(cs, 360000)
    m, rem = divmod(rem, 6000)
    s, cs = divmod(rem, 100)
    return f"{h:d}:{m:02d}:{s:02d}.{cs:02d}"


def group_lines(words, max_words=4, max_dur=3.0):
    """Group words into caption chunks broken on punctuation or length."""
    lines, cur = [], []
    for i, (s, e, w) in enumerate(words):
        cur.append((s, e, w))
        ends_sentence = w.rstrip().endswith((".", "!", "?", "…", ":", ";"))
        too_long = len(cur) >= max_words or (cur[-1][1] - cur[0][0]) >= max_dur
        is_last = i == len(words) - 1
        if ends_sentence or too_long or is_last:
            lines.append(cur)
            cur = []
    if cur:
        lines.append(cur)
    return lines


def write_ass(words, path, dur):
    style = (
        "[Script Info]\n"
        "ScriptType: v4.00+\n"
        f"PlayResX: {W}\n"
        f"PlayResY: {H}\n"
        "WrapStyle: 0\n"
        "ScaledBorderAndShadow: yes\n\n"
        "[V4+ Styles]\n"
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, "
        "OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, "
        "ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, "
        "MarginL, MarginR, MarginV, Encoding\n"
        "Style: Cap,DejaVu Sans,88,&H00FFFFFF,&H00FFFFFF,&H00101010,&H64000000,"
        "-1,0,0,0,100,100,0,0,1,5,3,2,80,80,420,1\n\n"
        "[Events]\n"
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, "
        "Effect, Text\n"
    )
    body = []
    lines = group_lines(words)
    for idx, chunk in enumerate(lines):
        start = chunk[0][0]
        end = chunk[-1][1] + 0.12
        if idx + 1 < len(lines):
            end = min(end, lines[idx + 1][0][0])
        end = min(end, dur)
        text = " ".join(w for _, _, w in chunk).strip()
        text = text.replace("{", "(").replace("}", ")")
        body.append(
            f"Dialogue: 0,{ass_ts(start)},{ass_ts(end)},Cap,,0,0,0,,{text}"
        )
    with open(path, "w", encoding="utf-8") as f:
        f.write(style + "\n".join(body) + "\n")


def find_font():
    for p in (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf",
        "/Library/Fonts/Arial Bold.ttf",
    ):
        if os.path.exists(p):
            return p
    return None


def render(bg_gradient, voice_mp3, ass_path, meta, out_path, tmp):
    dur = ffprobe_duration(voice_mp3)
    font = find_font()

    handle_txt = os.path.join(tmp, "handle.txt")
    with open(handle_txt, "w", encoding="utf-8") as f:
        f.write(HANDLE)
    cta_txt = os.path.join(tmp, "cta.txt")
    with open(cta_txt, "w", encoding="utf-8") as f:
        f.write(meta.get("cta", "ссылка в описании"))

    vf = [f"noise=alls=6:allf=t", "vignette=PI/5"]
    # timecode-driven progress-ish brightness pulse (keeps it from looking static)
    vf.append("eq=brightness='0.02*sin(2*PI*t/6)':saturation=1.15")
    vf.append(f"subtitles=filename='{ass_path}'")
    if font:
        ff = font.replace(":", "\\:")
        vf.append(
            "drawtext=fontfile='%s':textfile='%s':x=(w-text_w)/2:y=120:"
            "fontsize=64:fontcolor=white@0.95:box=1:boxcolor=black@0.35:"
            "boxborderw=22" % (ff, cta_txt.replace(":", "\\:"))
        )
        vf.append(
            "drawtext=fontfile='%s':textfile='%s':x=(w-text_w)/2:y=h-170:"
            "fontsize=58:fontcolor=white@0.92:box=1:boxcolor=0x1D4ED8@0.75:"
            "boxborderw=20" % (ff, handle_txt.replace(":", "\\:"))
        )

    filter_complex = (
        f"[0:v]" + ",".join(vf) + "[v]"
    )
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i",
        f"gradients=s={W}x{H}:r={FPS}:c0=0x0B1220:c1=0x1D4ED8:c2=0x7C3AED:"
        f"speed=0.012:d={dur + 1:.2f}",
        "-i", voice_mp3,
        "-filter_complex", filter_complex,
        "-map", "[v]", "-map", "1:a",
        "-t", f"{dur:.2f}",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
        "-pix_fmt", "yuv420p", "-r", str(FPS),
        "-c:a", "aac", "-b:a", "192k",
        "-movflags", "+faststart",
        out_path,
    ]
    run(cmd)
    return dur


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--topics", default="content/topics.json")
    ap.add_argument("--topic", default=os.environ.get("TOPIC", ""))
    ap.add_argument("--out", default="out")
    args = ap.parse_args()

    with open(args.topics, encoding="utf-8") as f:
        topics = json.load(f)["topics"]

    topic = pick_topic(topics, args.topic or None)
    os.makedirs(args.out, exist_ok=True)
    print(f"== topic: {topic['id']} ==")

    script = "\n".join(topic["scenes"]).strip()
    voice = topic.get("voice", "ru-RU-DmitryNeural")

    with tempfile.TemporaryDirectory() as tmp:
        voice_mp3 = os.path.join(tmp, "voice.mp3")
        print("synthesizing speech...", flush=True)
        words = asyncio.run(synth(script, voice, voice_mp3))

        ass_path = os.path.join(tmp, "subs.ass")
        dur = ffprobe_duration(voice_mp3)
        write_ass(words, ass_path, dur)

        out_path = os.path.join(args.out, f"{topic['id']}.mp4")
        render(topic.get("background", ""), voice_mp3, ass_path, topic,
               out_path, tmp)

        meta = {
            "id": topic["id"],
            "title": topic["title"],
            "description": topic["description"],
            "tags": topic.get("tags", []),
            "file": out_path,
            "duration": round(dur, 2),
        }
        meta_path = os.path.join(args.out, f"{topic['id']}.json")
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)

    print(f"done: {meta['file']} ({meta['duration']}s)")
    print(f"WROTE {meta_path}")


if __name__ == "__main__":
    sys.exit(main())
