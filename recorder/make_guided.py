"""The Guided Audio Bible: one video per book with an original introduction, chapter titles, a KJV word helper,
well-known passage markers, a "where we are" line and a short outro, around the unchanged recorded reading.

  python recorder/make_guided.py --book 0 --dir rec/00 --out guided [--only 1,2,3]
  -> guided/01-Genesis.mp4  and guided/01-Genesis.json (where each chapter starts, for the description's timestamps)

Book scripts live in recorder/guide/NN-name.json; old words and their meanings in recorder/kjv_words.json.
"""
import argparse, glob, json, math, os, re, subprocess, tempfile
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

SR, W, H, FPS = 24000, 1280, 720, 10
PAUSE = 2.0                       # between chapters (as in the plain videos)
HERE = os.path.dirname(os.path.abspath(__file__))


def ts(s):
    return f"{int(s // 3600)}:{int(s % 3600 // 60):02d}:{s % 60:05.2f}"


def esc(t):
    return t.replace("\\", "").replace("{", "(").replace("}", ")").replace("\n", " ")


def silence(sec):
    return np.zeros(int(round(sec * SR)), dtype=np.float32)


SAY = [(" read aloud", " red aloud"), (" read out loud", " red out loud")]   # past tense "read" said as "red"


def tts(k, text, voice="am_onyx", speed=0.88, lang="en-us"):
    text = re.sub(r"\bread (aloud|together|out loud)", r"red \1", text)   # past tense "read" is said "red"
    a, sr = k.create(text, voice=voice, speed=speed, lang=lang)
    assert sr == SR
    return a.astype(np.float32)


def symbol(d, kind, col):
    """A simple line symbol for the book, drawn large and faint on the right."""
    if kind == "tree":
        d.rectangle([1040, 300, 1072, 640], fill=col)
        for cx, cy, r in ((1056, 250, 150), (960, 330, 100), (1150, 330, 100), (1056, 380, 110)):
            d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=col)
    elif kind == "waves":
        for k in range(5):
            y = 360 + k * 60
            d.line([(x, y + 22 * math.sin(x / 70)) for x in range(820, 1281, 8)], fill=col, width=10)
    elif kind == "mountain":
        d.polygon([(780, 680), (1000, 300), (1220, 680)], fill=col); d.polygon([(960, 680), (1130, 400), (1290, 680)], fill=col)
    elif kind == "tablets":
        for x in (900, 1070):
            d.rounded_rectangle([x, 260, x + 150, 560], radius=60, fill=col)
    elif kind == "tent":
        d.polygon([(860, 620), (1040, 330), (1220, 620)], fill=col); d.line([(1040, 330), (1040, 250)], fill=col, width=10)
    elif kind == "crown":
        d.polygon([(860, 560), (880, 340), (960, 450), (1040, 300), (1120, 450), (1200, 340), (1220, 560)], fill=col)
    elif kind == "harp":
        d.arc([860, 260, 1220, 620], 180, 360, fill=col, width=16)
        for x in range(900, 1200, 40):
            d.line([(x, 440), (x, 300 + abs(1040 - x) // 3)], fill=col, width=5)
        d.line([(860, 440), (1220, 440)], fill=col, width=14)
    elif kind == "scroll":
        d.rectangle([880, 300, 1200, 560], fill=col)
        for y in (290, 570):
            d.ellipse([860, y - 25, 1220, y + 25], fill=col)
    elif kind == "city":
        for x, h in ((860, 260), (930, 340), (1010, 220), (1080, 380), (1160, 300)):
            d.rectangle([x, 680 - h, x + 60, 680], fill=col)
    elif kind == "dove":
        d.ellipse([920, 380, 1140, 470], fill=col); d.polygon([(980, 400), (1060, 250), (1100, 410)], fill=col); d.ellipse([1110, 360, 1170, 410], fill=col)
    elif kind == "cross":
        d.rectangle([1025, 240, 1075, 640], fill=col); d.rectangle([940, 330, 1160, 380], fill=col)
    elif kind == "star":
        pts = [(1040 + (150 if i % 2 == 0 else 60) * math.sin(i * math.pi / 5), 440 - (150 if i % 2 == 0 else 60) * math.cos(i * math.pi / 5)) for i in range(10)]
        d.polygon(pts, fill=col)
    elif kind == "flame":
        d.polygon([(1040, 230), (1150, 420), (1120, 560), (1040, 600), (960, 560), (930, 430), (1000, 340), (1020, 420)], fill=col)
    elif kind == "lamp":
        d.ellipse([900, 480, 1180, 580], fill=col); d.polygon([(1040, 330), (1070, 420), (1040, 470), (1010, 420)], fill=col)
    elif kind == "sheep":
        for cx, cy, r in ((1000, 450, 80), (1080, 440, 85), (1150, 460, 70), (1040, 500, 80)):
            d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=col)
        d.ellipse([1180, 400, 1260, 470], fill=col)
    elif kind == "wall":
        for row in range(5):
            for col_ in range(4):
                x = 860 + col_ * 95 + (45 if row % 2 else 0); y = 420 + row * 55
                d.rectangle([x, y, x + 85, y + 45], fill=col)
    else:                         # a simple open book
        d.polygon([(860, 420), (1060, 380), (1060, 600), (860, 640)], fill=col)
        d.polygon([(1080, 380), (1260, 420), (1260, 640), (1080, 600)], fill=col)


def background(spec, path):
    c0, c1, c2 = [tuple(x) for x in spec.get("palette", [[16, 20, 36], [40, 44, 90], [150, 120, 70]])]
    img = Image.new("RGB", (W, H)); d = ImageDraw.Draw(img)
    for y in range(H):
        f = y / H
        d.line([(0, y), (W, y)], fill=tuple(int(c0[i] + (c1[i] - c0[i]) * min(1, f * 1.4) + (c2[i] - c1[i]) * max(0, f * 1.4 - 1) * 1.6) for i in range(3)))
    glow = Image.new("L", (W, H), 0)
    ImageDraw.Draw(glow).ellipse([-300, -420, 760, 380], fill=60)
    img = Image.composite(Image.new("RGB", (W, H), (255, 236, 200)), img, glow.filter(ImageFilter.GaussianBlur(160)))
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0)); symbol(ImageDraw.Draw(layer), spec.get("symbol", "book"), (255, 255, 255, 14))
    img = Image.alpha_composite(img.convert("RGBA"), layer.filter(ImageFilter.GaussianBlur(2))).convert("RGB")
    img.save(path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--book", type=int, required=True)
    ap.add_argument("--dir", required=True)
    ap.add_argument("--bible", default="bible/kjv.json")
    ap.add_argument("--models", default="models")
    ap.add_argument("--fonts", default=os.path.join(HERE, "fonts"))
    ap.add_argument("--out", default="guided")
    ap.add_argument("--only", default="", help="pilot: just these chapters, e.g. 1,2,3")
    a = ap.parse_args()
    from kokoro_onnx import Kokoro
    k = Kokoro(f"{a.models}/kokoro-v1.0.onnx", f"{a.models}/voices-v1.0.bin")
    bible = json.load(open(a.bible))
    words = {w: v for w, v in json.load(open(os.path.join(HERE, "kjv_words.json"))).items() if not w.startswith("_")}
    spec = json.load(open(glob.glob(os.path.join(HERE, "guide", f"{a.book:02d}-*.json"))[0]))
    bi, (name, chapters) = a.book, bible[a.book]
    disp = spec.get("display", f"the book of {name}")
    if not spec["intro"][-1].startswith("This is"):
        spec["intro"].append(f"This is {disp}, from the King James Bible. Old words are explained on screen as we go.")
    if "outro" not in spec:      # said slowly, one sentence at a time
        spec["outro"] = [f"That's {disp}.", f"Next in this series: {spec['next_say']}.", "Leave a comment, and share your thoughts below.",
                         "If you enjoyed this reading, please like and subscribe. It helps others find the Bible, read aloud.",
                         "And join others to hear the Bible read together, live, twenty-four seven, at Live Bible Reading dot com."]
    if a.only:
        keep = {int(x) for x in a.only.split(",")}
        chapters = [ch for ch in chapters if ch[0] in keep]
    big = "Psalms" if bi == 18 else name
    cname = lambda c: f"Psalm {c}" if bi == 18 else f"{name} {c}"
    nt, total_ch = bi >= 39, len(bible[bi][1])

    # ---------- the soundtrack ----------
    parts, t = [], 0.0
    def add(x):
        nonlocal t
        parts.append(x); t += len(x) / SR
    add(silence(0.8)); hook_at = t; add(tts(k, spec["hook"])); add(silence(0.5))
    add(tts(k, spec.get("lead", "Here's a quick introduction to what's ahead."))); add(silence(0.9))
    intro_at = t
    for line in spec["intro"]:
        add(tts(k, line)); add(silence(0.55))
    add(silence(1.2))
    starts, metas = [], []
    for j, (c, vs) in enumerate(chapters):
        m = json.load(open(f"{a.dir}/{bi:02d}-{c:03d}.json"))
        pcm = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", f"{a.dir}/{bi:02d}-{c:03d}.mp3", "-f", "s16le", "-ac", "1", "-ar", str(SR), "-"],
                             capture_output=True, check=True).stdout
        x = np.frombuffer(pcm, dtype=np.int16).astype(np.float32) / 32768
        want = int(round(m["duration"] * SR)); x = np.concatenate([x[:want], silence(max(0, want - len(x)) / SR)])
        starts.append(t); metas.append(m); add(x)
        if j < len(chapters) - 1: add(silence(PAUSE))
    add(silence(1.5)); outro_at = t
    for line in (spec["outro"] if isinstance(spec["outro"], list) else [spec["outro"]]):
        add(tts(k, line, speed=0.88)); add(silence(0.5))
    outro_end = t
    add(silence(20))             # room for YouTube's end screen (next video + subscribe)
    total = t
    audio = np.concatenate(parts); audio = np.clip(audio, -0.98, 0.98)
    work = tempfile.mkdtemp(prefix="lbrg-")
    raw = f"{work}/audio.raw"; (audio * 32767).astype(np.int16).tofile(raw)

    # ---------- what's on screen ----------
    gold, ink = "&H008CC9F0&", "&H00E8F1F5&"
    L = ["[Script Info]", "ScriptType: v4.00+", f"PlayResX: {W}", f"PlayResY: {H}", "WrapStyle: 0", "", "[V4+ Styles]",
         "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
         "Style: Verse,Literata,56,&H00F5F1E8,&H00F5F1E8,&H00000000,&H64000000,0,0,0,0,100,100,0,0,1,0,2,4,90,90,40,1",
         "Style: Title,IM FELL English SC,104,&H00F5F1E8,&H00F5F1E8,&H00000000,&H64000000,0,0,0,0,100,100,0,0,1,0,2,5,90,90,40,1",
         "Style: Card,IBM Plex Sans SemiBold,34,&H00F5F1E8,&H00F5F1E8,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,0,1,7,110,110,190,1",
         "Style: Top,IBM Plex Sans SemiBold,24,&H008CC9F0,&H008CC9F0,&H00000000,&H00000000,0,0,0,0,100,100,2,0,1,0,0,7,70,70,40,1",
         "Style: Foot,IBM Plex Sans SemiBold,22,&H00E8F1F5,&H00E8F1F5,&H00000000,&H00000000,0,0,0,0,100,100,1,0,1,0,0,1,70,70,36,1",
         "Style: Help,IBM Plex Sans SemiBold,28,&H00F5F1E8,&H00F5F1E8,&H00201814,&H00201814,0,0,0,0,100,100,0,0,3,14,0,3,70,70,70,1",
         "Style: Badge,IBM Plex Sans SemiBold,25,&H00141E20,&H00141E20,&H0057B6E4,&H0057B6E4,0,0,0,0,100,100,1,0,3,10,0,9,70,70,40,1",
         "", "[Events]", "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text"]
    ev = lambda layer, t0, t1, style, text: L.append(f"Dialogue: {layer},{ts(t0)},{ts(t1)},{style},,0,0,0,,{text}")
    ev(0, 0, total, "Foot", "{\\alpha&H40&}LiveBibleReading.com  ·  listen live, 24/7")
    # opening and introduction
    ev(1, 0.3, intro_at, "Title", f"{{\\fad(400,300)\\fs44}}The Book of\\N{{\\fs104}}{esc(big)}\\N{{\\fs36\\fnLiterata\\i1}}A quick introduction, then the full book")
    test = "OLD TESTAMENT" if not nt else "NEW TESTAMENT"
    ev(0, intro_at, starts[0], "Top", f"{test}  ·  BOOK {bi + 1} OF 66  ·  INTRODUCTION")
    cd = spec["card"]
    card = (f"{{\\fad(400,400)\\fs64\\fnIM FELL English SC\\c&HF5F1E8&}}{esc(big)}\\N{{\\fs26\\fnIBM Plex Sans SemiBold\\c{gold}}}BOOK {bi + 1} OF 66  ·  {total_ch} CHAPTERS\\N\\N"
            f"{{\\fs34\\c{ink}}}{{\\c{gold}}}Written by:{{\\c{ink}}} {esc(cd['who'])}\\N{{\\c{gold}}}How it's laid out:{{\\c{ink}}} {esc(cd['parts']).replace(' | ', '\\N' + '\\h' * 22)}\\N"
            f"{{\\c{gold}}}Key passages:{{\\c{ink}}} {esc(cd['key'])}\\N{{\\c{gold}}}Listen for:{{\\c{ink}}} {esc(cd['listen'])}")
    ev(1, intro_at, starts[0] - 0.4, "Card", card)
    # the reading
    seen_once, helper_free = set(), 0.0
    famous = spec.get("famous", {})
    for j, ((c, vs), m, s0) in enumerate(zip(chapters, metas, starts)):
        end = starts[j + 1] if j + 1 < len(starts) else outro_at
        title = spec["titles"].get(str(c), "")
        ev(0, s0, end, "Top", f"{test}  ·  BOOK {bi + 1} OF 66  ·  {esc(cname(c).upper())} OF {total_ch}" + (f"  ·  {esc(title.upper())}" if title else ""))
        marks = m["verses"]; first = marks[0][1] if marks else 2
        ev(1, s0, s0 + max(first, 2.5), "Title", f"{{\\fad(300,300)}}{esc(cname(c))}\\N{{\\fs44\\fnLiterata\\i1}}{esc(title)}")
        if str(c) in famous:
            ev(2, s0 + 0.5, s0 + 9, "Badge", f"{{\\fad(300,300)}}★ Well-known: {esc(famous[str(c)])}")
        seen_ch = set()
        for kk, (v, t0) in enumerate(marks):
            t1 = marks[kk + 1][1] if kk + 1 < len(marks) else m["duration"] + PAUSE * 0.5
            text = esc(vs[kk][1]) if kk < len(vs) else ""
            n = len(text)
            size = 64 if n < 90 else 56 if n < 160 else 48 if n < 260 else 41 if n < 380 else 35
            ev(1, s0 + t0, s0 + t1, "Verse", f"{{\\fs{size}\\fad(200,0)}}{{\\fs{int(size * .5)}\\c&H8CC9F0&}}{v} {{\\fs{size}\\c&HE8F1F5&}}{text}")
            key = f"{c}:{v}"
            if key in famous:
                ev(2, s0 + t0, s0 + t0 + 8, "Badge", f"{{\\fad(300,300)}}★ Well-known: {esc(famous[key])}")
            if s0 + t0 < helper_free:
                continue
            for w in re.findall(r"[A-Za-z]+", text):
                lw = w.lower(); g = words.get(lw)
                if not g: continue
                tag = g["say"]
                if (g.get("once") and tag in seen_once) or tag in seen_ch: continue
                seen_ch.add(tag); seen_once.add(tag)
                ev(3, s0 + t0 + 0.4, s0 + t0 + 6.4, "Help", f"{{\\fad(250,250)}}{{\\c{gold}}}{esc(tag)}{{\\c&HF5F1E8&}} = {esc(g['mean'])}")
                helper_free = s0 + t0 + 7
                break
    # outro and end-screen space
    ev(0, outro_at, total, "Top", f"{test}  ·  BOOK {bi + 1} OF 66  ·  THANK YOU FOR LISTENING")
    ev(1, outro_at, outro_end + 1, "Card",
       f"{{\\fad(400,400)\\fs54\\fnIM FELL English SC}}The end of {esc(big)}\\N\\N{{\\fs32\\fnIBM Plex Sans SemiBold\\c{gold}}}Next in this series:{{\\c{ink}}} {esc(spec['next'])}\\N"
       f"{{\\c{gold}}}Comments:{{\\c{ink}}} share your thoughts below\\N{{\\c{gold}}}Like & subscribe:{{\\c{ink}}} it helps others find the Bible read aloud\\N{{\\c{gold}}}Live, 24/7:{{\\c{ink}}} hear it together at LiveBibleReading.com")
    ev(1, outro_end + 1, total, "Card", f"{{\\fad(400,0)\\fs40\\fnIM FELL English SC}}Keep listening\\N{{\\fs28\\fnIBM Plex Sans SemiBold\\c{ink}}}The whole Bible, in order, with every word on screen.")
    ass = f"{work}/book.ass"; open(ass, "w").write("\n".join(L) + "\n")
    bg = f"{work}/bg.png"; background(spec, bg)
    os.makedirs(a.out, exist_ok=True)
    base = f"{a.out}/{bi + 1:02d}-{name.replace(' ', '-')}"
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-loop", "1", "-framerate", str(FPS), "-i", bg,
                    "-f", "s16le", "-ar", str(SR), "-ac", "1", "-i", raw,
                    "-filter_complex", f"[0:v]ass={ass}:fontsdir={a.fonts},format=yuv420p[v];[1:a]aresample=48000[a]",
                    "-map", "[v]", "-map", "[a]", "-t", f"{total:.2f}", "-c:v", "libx264", "-preset", "veryfast", "-tune", "stillimage",
                    "-crf", "28", "-r", str(FPS), "-g", str(FPS * 10), "-c:a", "aac", "-b:a", "80k", "-ac", "1", "-movflags", "+faststart", base + ".mp4"], check=True)
    json.dump({"intro": 0, "chapters": [[c, round(s, 2)] for (c, _), s in zip(chapters, starts)], "outro": round(outro_at, 2), "total": round(total, 2)},
              open(base + ".json", "w"))
    print(base + ".mp4", f"{total / 60:.1f} min")


if __name__ == "__main__":
    main()
