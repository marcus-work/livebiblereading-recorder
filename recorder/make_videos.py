"""Makes one YouTube video per Bible book from the finished recordings: the verse on screen as it's read.

  python recorder/make_videos.py --book 7 --dir rec/07 --out videos
  -> videos/08-Ruth.mp4  (720p, 10 frames a second: light files, crisp text)

Chapters follow each other with a 2-second pause. chapter_starts() gives the exact second each chapter
begins, which kit.py uses for the YouTube chapter timestamps, so the two always agree.
"""
import argparse, json, os, subprocess, tempfile
from PIL import Image, ImageDraw, ImageFilter

PAUSE = 2.0
W, H, FPS = 1280, 720, 10
HERE = os.path.dirname(os.path.abspath(__file__))


def chapter_starts(durations):
    t, out = 0.0, []
    for d in durations:
        out.append(t)
        t += d + PAUSE
    return out, t - PAUSE


def background(bi, path):
    nt = bi >= 39
    c0, c1, c2 = ((10, 14, 34), (28, 30, 70), (70, 48, 92)) if nt else ((26, 16, 12), (70, 40, 22), (120, 72, 36))
    img = Image.new("RGB", (W, H)); d = ImageDraw.Draw(img)
    for y in range(H):
        f = y / H
        d.line([(0, y), (W, y)], fill=tuple(int(c0[i] + (c1[i] - c0[i]) * min(1, f * 1.6) + (c2[i] - c1[i]) * max(0, f * 1.6 - 1) / 0.6) for i in range(3)))
    glow = Image.new("L", (W, H), 0)
    ImageDraw.Draw(glow).ellipse([-300, -420, 700, 380], fill=70)
    img = Image.composite(Image.new("RGB", (W, H), (255, 240, 210)), img, glow.filter(ImageFilter.GaussianBlur(160)))
    img.save(path)


def ts(s):
    return f"{int(s // 3600)}:{int(s % 3600 // 60):02d}:{s % 60:05.2f}"


def esc(t):
    return t.replace("\\", "").replace("{", "(").replace("}", ")").replace("\n", " ")


def make(bi, folder, bible, out_dir, fonts):
    name, chapters = bible[bi]
    keys = [f"{bi:02d}-{c:03d}" for c, _ in chapters]
    metas = [json.load(open(f"{folder}/{k}.json")) for k in keys]
    starts, total = chapter_starts([m["duration"] for m in metas])
    work = tempfile.mkdtemp(prefix="lbrv-")
    # audio: each chapter decoded and trimmed/padded to its exact length, joined with a short pause (exact timestamps)
    raw = f"{work}/audio.raw"
    with open(raw, "wb") as f:
        for j, (k, m) in enumerate(zip(keys, metas)):
            pcm = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", f"{folder}/{k}.mp3", "-f", "s16le", "-ac", "1", "-ar", "24000", "-"],
                                 capture_output=True, check=True).stdout
            want = int(round(m["duration"] * 24000)) * 2
            pcm = pcm[:want] + b"\0" * max(0, want - len(pcm))
            f.write(pcm)
            if j < len(keys) - 1: f.write(b"\0" * int(PAUSE * 24000) * 2)
    # words on screen
    L = ["[Script Info]", "ScriptType: v4.00+", f"PlayResX: {W}", f"PlayResY: {H}", "WrapStyle: 0", "", "[V4+ Styles]",
         "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
         "Style: Verse,Literata,56,&H00F5F1E8,&H00F5F1E8,&H00000000,&H64000000,0,0,0,0,100,100,0,0,1,0,2,4,90,90,40,1",
         "Style: Title,IM FELL English SC,100,&H00F5F1E8,&H00F5F1E8,&H00000000,&H64000000,0,0,0,0,100,100,0,0,1,0,2,5,90,90,40,1",
         "Style: Top,IBM Plex Sans SemiBold,26,&H008CC9F0,&H008CC9F0,&H00000000,&H00000000,0,0,0,0,100,100,3,0,1,0,0,7,70,70,46,1",
         "Style: Foot,IBM Plex Sans SemiBold,24,&H00E8F1F5,&H00E8F1F5,&H00000000,&H00000000,0,0,0,0,100,100,1,0,1,0,0,1,70,70,40,1",
         "", "[Events]", "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
         f"Dialogue: 0,{ts(0)},{ts(total)},Foot,,0,0,0,,{{\\alpha&H40&}}Hear it live, together, 24/7 at LiveBibleReading.com"]
    for j, ((c, vs), m, s0) in enumerate(zip(chapters, metas, starts)):
        end = starts[j + 1] if j + 1 < len(starts) else total
        label = f"Psalm {c}" if bi == 18 else f"{name} {c}"
        L.append(f"Dialogue: 0,{ts(s0)},{ts(end)},Top,,0,0,0,,{esc(label.upper())}   ·   KING JAMES VERSION")
        marks = m["verses"]
        first = marks[0][1] if marks else 2
        big = "Psalms" if bi == 18 else name
        sub = f"Psalm {c}" if bi == 18 else f"Chapter {c}"
        L.append(f"Dialogue: 1,{ts(s0)},{ts(s0 + first)},Title,,0,0,0,,{{\\fad(300,300)}}{esc(big)}\\N{{\\fs44\\fnLiterata\\i1}}{sub}")
        for k, (v, t0) in enumerate(marks):
            t1 = marks[k + 1][1] if k + 1 < len(marks) else m["duration"] + PAUSE * 0.5
            text = esc(vs[k][1]) if k < len(vs) else ""
            n = len(text)
            size = 64 if n < 90 else 56 if n < 160 else 48 if n < 260 else 41 if n < 380 else 35
            L.append(f"Dialogue: 1,{ts(s0 + t0)},{ts(s0 + t1)},Verse,,0,0,0,,{{\\fs{size}\\fad(200,0)}}{{\\fs{int(size * .5)}\\c&H8CC9F0&}}{v} {{\\fs{size}\\c&HE8F1F5&}}{text}")
    ass = f"{work}/book.ass"
    open(ass, "w").write("\n".join(L) + "\n")
    bg = f"{work}/bg.png"; background(bi, bg)
    os.makedirs(out_dir, exist_ok=True)
    out = f"{out_dir}/{bi + 1:02d}-{name.replace(' ', '-')}.mp4"
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                    "-loop", "1", "-framerate", str(FPS), "-i", bg,
                    "-f", "s16le", "-ar", "24000", "-ac", "1", "-i", raw,
                    "-filter_complex", f"[0:v]ass={ass}:fontsdir={fonts},format=yuv420p[v];[1:a]aresample=48000[a]",
                    "-map", "[v]", "-map", "[a]", "-t", f"{total + 1:.2f}",
                    "-c:v", "libx264", "-preset", "veryfast", "-tune", "stillimage", "-crf", "28", "-r", str(FPS), "-g", str(FPS * 10),
                    "-c:a", "aac", "-b:a", "80k", "-ac", "1", "-movflags", "+faststart", out], check=True)
    try: os.remove(raw)
    except OSError: pass
    return out, total


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--book", type=int, required=True)
    ap.add_argument("--dir", required=True)
    ap.add_argument("--bible", default="bible/kjv.json")
    ap.add_argument("--fonts", default=os.path.join(HERE, "fonts"))
    ap.add_argument("--out", default="videos")
    a = ap.parse_args()
    path, secs = make(a.book, a.dir, json.load(open(a.bible)), a.out, a.fonts)
    print(path, f"{secs / 3600:.2f} h")
