"""YouTube Shorts from the recorded reading: a spoken hook, the verse(s) in big type with each word lighting up as
the narrator reads it, and a hand-off to the full book video. Vertical 1080x1920, 20-50 seconds.

  python recorder/make_short.py --batch recorder/shorts/december.json --dir rec --out shorts [--only advent-01,sleep-ps4]
  rec/ holds the recordings (BB-CCC.mp3 and BB-CCC.json) for every book the batch uses.
  -> shorts/<date>-<id>.mp4, plus shorts/shorts.json (titles, descriptions, tags, schedule) for the upload desk.
"""
import argparse, json, math, os, re, subprocess, tempfile
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
SR, FPS, W, H = 24000, 30, 1080, 1920
CHANNEL = "https://www.youtube.com/@LiveBibleReadingCom"
GOLD, INK, DIM = "&H0057B6E4", "&H00DEEEF5", "&H00968482"     # ASS colours are BGR


def ts(s):
    return f"{int(s // 3600)}:{int(s % 3600 // 60):02d}:{s % 60:05.2f}"


def esc(t):
    return t.replace("\\", "").replace("{", "(").replace("}", ")").replace("\n", " ")


def tts(k, text, speed=0.9):
    a, sr = k.create(text, voice="am_onyx", speed=speed, lang="en-us")
    return a.astype(np.float32)


def decode(mp3):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", mp3, "-f", "f32le", "-ac", "1", "-ar", str(SR), "-"], capture_output=True, check=True).stdout
    return np.frombuffer(raw, dtype=np.float32)


def background(path, series):
    """Night sky: deep navy to warm dark, a candle-gold glow low in the frame (a star for Advent)."""
    img = Image.new("RGB", (W, H)); d = ImageDraw.Draw(img)
    for y in range(H):
        f = y / H
        d.line([(0, y), (W, y)], fill=(int(12 + 22 * f), int(16 + 12 * f), int(34 - 10 * f)))
    glow = Image.new("L", (W, H), 0); g = ImageDraw.Draw(glow)
    if series == "Advent":
        g.ellipse([290, 120, 790, 620], fill=60)                     # starlight from above
        glow = glow.filter(ImageFilter.GaussianBlur(140))
    else:
        g.ellipse([140, 1000, 940, 1800], fill=70)                   # candle glow from below
        glow = glow.filter(ImageFilter.GaussianBlur(160))
    img = Image.composite(Image.new("RGB", (W, H), (228, 166, 80)), img, glow)
    if series == "Advent":                                          # a small four-point star
        s = ImageDraw.Draw(img); cx, cy, r = 540, 330, 34
        s.polygon([(cx, cy - r), (cx + 7, cy - 7), (cx + r, cy), (cx + 7, cy + 7), (cx, cy + r), (cx - 7, cy + 7), (cx - r, cy), (cx - 7, cy - 7)], fill=(246, 222, 160))
    img.save(path)


def karaoke(text, length):
    """Each word lights up in turn over the verse's spoken length (spread by word length)."""
    words = text.split()
    weights = [len(re.sub(r"\W", "", w)) + 2 for w in words]
    total = sum(weights); lead = 0.15; span = max(length - lead, 0.5)
    out, used = [f"{{\\k{int(lead * 100)}}}"], 0
    for w, wt in zip(words, weights):
        cs = max(1, int(round(span * wt / total * 100)))
        out.append(f"{{\\kf{cs}}}{esc(w)} ")
    return "".join(out).rstrip()


def verse_size(n):
    return 84 if n < 80 else 76 if n < 130 else 68 if n < 190 else 60 if n < 260 else 54


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--batch", required=True); ap.add_argument("--dir", required=True); ap.add_argument("--out", required=True)
    ap.add_argument("--only", default="")
    ap.add_argument("--fonts", default=os.path.join(HERE, "fonts"))
    a = ap.parse_args()
    from kokoro_onnx import Kokoro
    root = os.path.dirname(HERE)
    k = Kokoro(os.path.join(root, "models/kokoro-v1.0.onnx"), os.path.join(root, "models/voices-v1.0.bin"))
    bible = json.load(open(os.path.join(root, "bible/kjv.json")))
    batch = json.load(open(a.batch)); only = set(x for x in a.only.split(",") if x)
    os.makedirs(a.out, exist_ok=True)
    meta = []
    for s in batch["shorts"]:
        if only and s["id"] not in only:
            continue
        bi, c, v1, v2 = s["ref"]; book = bible[bi][0]
        verses = dict(bible[bi][1][c - 1][1])
        texts = [(v, verses[v]) for v in range(v1, v2 + 1)]
        bookname = "Psalm" if bi == 18 else book
        ref = f"{bookname} {c}:{v1}" + (f"–{v2}" if v2 != v1 else "")
        rec = json.load(open(f"{a.dir}/{bi:02d}-{c:03d}.json"))
        marks = {v: (t, rec["lengths"][i]) for i, (v, t) in enumerate(rec["verses"])}
        audio = decode(f"{a.dir}/{bi:02d}-{c:03d}.mp3")
        whole = "the Book of Psalms" if bi == 18 else f"the Book of {book}"
        advent = s.get("series") == "Advent"

        parts, t = [], 0.0
        def add(x):
            nonlocal t
            parts.append(x); t += len(x) / SR
        add(np.zeros(int(SR * 0.25), np.float32))
        hook_at = t; add(tts(k, s["hook"].replace("…", "."))); hook_end = t
        add(np.zeros(int(SR * 0.45), np.float32))
        lines = []
        for v, text in texts:
            st, ln = marks[v]
            seg = audio[int(st * SR): int((st + ln + 0.05) * SR)]
            lines.append((t, t + len(seg) / SR, v, text)); add(seg); add(np.zeros(int(SR * 0.35), np.float32))
        end_say = f"Hear {whole}, read aloud, on this channel." if not advent else f"Day {s['day']} of 24. The whole of {book} is on this channel."
        end_at = t; add(tts(k, end_say)); add(np.zeros(int(SR * 1.4), np.float32))
        total = t
        if total > 58:
            print(f"  ! {s['id']} is {total:.1f}s (over 58s)")

        L = ["[Script Info]", "ScriptType: v4.00+", f"PlayResX: {W}", f"PlayResY: {H}", "WrapStyle: 0", "",
             "[V4+ Styles]", "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
             f"Style: Brand,IBM Plex Sans SemiBold,34,{GOLD},{GOLD},&H00000000,&H00000000,0,0,0,0,100,100,4,0,1,0,0,8,60,60,150,1",
             f"Style: Hook,IBM Plex Sans SemiBold,80,{INK},{INK},&H00000000,&H64000000,0,0,0,0,100,100,0,0,1,0,3,5,90,90,0,1",
             f"Style: Verse,Literata,72,{INK},{DIM},&H00000000,&H64000000,0,0,0,0,100,100,0,0,1,0,3,5,90,90,0,1",
             f"Style: Ref,IM FELL English SC,60,{GOLD},{GOLD},&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,0,0,5,60,60,0,1",
             f"Style: End,IBM Plex Sans SemiBold,64,{INK},{INK},&H00000000,&H64000000,0,0,0,0,100,100,0,0,1,0,3,5,90,90,0,1",
             "", "[Events]", "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text"]
        ev = lambda st, a_, b_, txt, lay=1: L.append(f"Dialogue: {lay},{ts(a_)},{ts(b_)},{st},,0,0,0,,{txt}")
        ev("Brand", 0, total, "LIVE BIBLE READING", 0)
        if advent:
            ev("Brand", 0, total, f"{{\\pos(540,440)\\fs40\\c{INK}}}ADVENT · DAY {s['day']} OF 24", 0)
        ev("Hook", hook_at, lines[0][0] - 0.05, f"{{\\pos(540,860)\\fad(150,150)}}{esc(s['hook'])}")
        ev("Ref", hook_at, lines[0][0] - 0.05, f"{{\\pos(540,1110)\\fad(150,150)}}{esc(ref)}")
        for i, (a_, b_, v, text) in enumerate(lines):
            nxt = lines[i + 1][0] if i + 1 < len(lines) else end_at
            ev("Verse", a_, nxt - 0.02, f"{{\\pos(540,820)\\fs{verse_size(len(text))}\\fad(120,0)}}" + karaoke(text, b_ - a_))
        ev("Ref", lines[0][0], end_at, f"{{\\pos(540,1290)}}{esc(ref)} · KJV")
        if advent:
            end_txt = (f"{{\\pos(540,760)\\fad(200,0)}}Hear the whole Book of {esc(book)}\\N{{\\fs52\\c{GOLD}\\fnLiterata\\i1}}read aloud, on this channel"
                       f"\\N\\N{{\\fs46\\c{INK}\\i0\\fnIBM Plex Sans SemiBold}}Subscribe: a verse every morning\\Nuntil Christmas")
        else:
            end_txt = (f"{{\\pos(540,760)\\fad(200,0)}}Hear {esc(whole)}\\N{{\\fs52\\c{GOLD}\\fnLiterata\\i1}}read aloud, on this channel"
                       f"\\N\\N{{\\fs46\\c{INK}\\i0\\fnIBM Plex Sans SemiBold}}Subscribe for a verse every day")
        ev("End", end_at, total, end_txt)

        name = f"{s['date']}-{s['id']}"
        with tempfile.TemporaryDirectory() as tmp:
            bg = f"{tmp}/bg.png"; background(bg, s.get("series"))
            ass = f"{tmp}/s.ass"; open(ass, "w").write("\n".join(L) + "\n")
            raw = f"{tmp}/a.raw"; np.clip(np.concatenate(parts), -0.98, 0.98).astype(np.float32).tofile(raw)
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-loop", "1", "-framerate", str(FPS), "-i", bg,
                            "-f", "f32le", "-ar", str(SR), "-ac", "1", "-i", raw,
                            "-filter_complex", f"[0:v]ass={ass}:fontsdir={a.fonts},format=yuv420p[v];[1:a]loudnorm=I=-14:TP=-1.5:LRA=11,aresample=48000[a]",
                            "-map", "[v]", "-map", "[a]", "-t", f"{total:.2f}", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
                            "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", f"{a.out}/{name}.mp4"], check=True)

        verse_text = " ".join(f"{v} {t_}" for v, t_ in texts)
        if advent:
            title = f"Advent Day {s['day']}: {s['hook']} ({ref}) #Shorts"
            tags = ["#Advent", "#Christmas", "#Bible"]
            series_line = f"Advent: 24 days of Scripture before Christmas. Day {s['day']} of 24. Subscribe for tomorrow's verse."
        else:
            title = f"{s['hook']} {ref} #Shorts"
            tags = ["#BibleVerse", "#Bible", "#Jesus"]
            series_line = "A verse every day. Subscribe so you don't miss tomorrow's."
        if len(title) > 100:
            title = f"{s['hook']} #Shorts"[:100]
        desc = "\n".join([f"{ref} (KJV)", "", verse_text, "",
                          f"🎧 Hear {whole}, read aloud in full: tap the related video above.", series_line,
                          "📤 Send this to someone who needs it today.", "",
                          "🕯 The whole Bible is also read aloud live, 24/7, at LiveBibleReading.com", "",
                          " ".join(tags + ["#KJV", "#Shorts"])])
        meta.append({"id": s["id"], "file": f"{name}.mp4", "date": s["date"], "time": s["time"], "series": s.get("series"),
                     "title": title, "desc": desc, "related": f"{bi + 1:02d}-{book.replace(' ', '-')}", "related_book": book,
                     "ref": ref, "seconds": round(total, 1)})
        print(f"{name}.mp4  {total:.1f}s  {ref}", flush=True)
    meta.sort(key=lambda m: (m["date"], m["time"]))
    json.dump(meta, open(f"{a.out}/shorts.json", "w"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
