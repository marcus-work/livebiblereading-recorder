"""YouTube show kit: thumbnails, show artwork, titles, descriptions with chapter timestamps, upload guide.

  python recorder/kit.py --index results/kjv-onyx-1/index.json --out youtube-kit
"""
import argparse, csv, json, os, re
from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
F = lambda name, size: ImageFont.truetype(os.path.join(HERE, "fonts", name), size)
PAUSE = 2.0
W, H = 1280, 720
SITE = "https://livebiblereading.com"
slug = lambda n: re.sub(r"[^a-z0-9]+", "-", n.lower()).strip("-")


def hms(s):
    s = int(s)
    return f"{s // 3600}:{s % 3600 // 60:02d}:{s % 60:02d}" if s >= 3600 else f"{s // 60}:{s % 60:02d}"


def nice_len(s):
    h, m = int(s // 3600), int(round(s % 3600 / 60))
    return f"{h} h {m} min" if h else f"{m} min"


def gradient(nt, w=W, h=H):
    c0, c1, c2 = ((10, 14, 34), (34, 34, 84), (92, 58, 110)) if nt else ((24, 14, 10), (78, 42, 20), (150, 88, 40))
    img = Image.new("RGB", (w, h)); d = ImageDraw.Draw(img)
    for x in range(w):                      # diagonal feel: left dark to right warm
        f = x / w
        col = tuple(int(c0[i] + (c1[i] - c0[i]) * min(1, f * 1.5) + (c2[i] - c1[i]) * max(0, f * 1.5 - 1) * 2) for i in range(3))
        d.line([(x, 0), (x, h)], fill=col)
    glow = Image.new("L", (w, h), 0)
    ImageDraw.Draw(glow).ellipse([int(w * .45), int(-h * .5), int(w * 1.3), int(h * .9)], fill=90)
    return Image.composite(Image.new("RGB", (w, h), (255, 226, 170)), img, glow.filter(ImageFilter.GaussianBlur(int(w * .12))))


def flame(d, x, y, s, gold=(228, 182, 87), ink=(245, 241, 232)):
    # the site's flame-and-lamp mark, drawn simply
    d.polygon([(x + 16 * s, y + 2 * s), (x + 22.6 * s, y + 13 * s), (x + 21 * s, y + 20 * s), (x + 16 * s, y + 21.5 * s), (x + 11 * s, y + 20 * s),
               (x + 9.4 * s, y + 14 * s), (x + 12.3 * s, y + 8 * s), (x + 14.5 * s, y + 11 * s)], fill=gold)
    d.polygon([(x + 5 * s, y + 24.5 * s), (x + 27 * s, y + 24.5 * s), (x + 23.8 * s, y + 29 * s), (x + 8.2 * s, y + 29 * s)], fill=ink)


def fit(d, text, font_name, max_w, start, min_size=60):
    size = start
    while size > min_size:
        f = F(font_name, size)
        if d.textlength(text, font=f) <= max_w: return f
        size -= 4
    return F(font_name, min_size)


def thumbnail(name, bi, season, ep, length, path):
    nt = bi >= 39
    img = gradient(nt); d = ImageDraw.Draw(img)
    ink, gold = (245, 241, 232), (240, 201, 140)
    flame(d, 70, 52, 2.4)
    d.text((160, 70), "LIVE BIBLE READING", font=F("IBMPlexSans-SemiBold.ttf", 30), fill=ink)
    d.text((160, 108), "The whole book, read aloud", font=F("Literata-Italic.ttf", 30), fill=gold)
    big = "Psalms" if bi == 18 else name
    f = fit(d, big, "IMFellEnglishSC-Regular.ttf", W - 160, 230)
    bb = d.textbbox((0, 0), big, font=f)
    y = 330 - (bb[3] - bb[1]) // 2
    d.text((82, y + 4), big, font=f, fill=(0, 0, 0, 120))
    d.text((80, y), big, font=f, fill=ink)
    d.rectangle([80, 560, 200, 565], fill=gold)
    small = F("IBMPlexSans-SemiBold.ttf", 34)
    d.text((80, 590), f"KING JAMES VERSION  ·  S{season} · E{ep}", font=small, fill=ink)
    tag = nice_len(length)
    tw = d.textlength(tag, font=small)
    d.rounded_rectangle([W - 110 - tw, 580, W - 70, 640], radius=12, fill=(0, 0, 0))
    d.text((W - 90 - tw, 590), tag, font=small, fill=(255, 255, 255))
    img.save(path, quality=90)


def show_art(path, w, h):
    img = gradient(False, w, h); d = ImageDraw.Draw(img)
    s = w / 1280
    flame(d, int(80 * s), int(70 * s), 3.2 * s)
    d.text((int(200 * s), int(95 * s)), "LIVE BIBLE READING", font=F("IBMPlexSans-SemiBold.ttf", int(40 * s)), fill=(245, 241, 232))
    t1 = "The Whole Bible"
    f = fit(d, t1, "IMFellEnglishSC-Regular.ttf", int(w * .86), int(190 * s), 40)
    d.text((int(80 * s), int(h * .36)), t1, font=f, fill=(245, 241, 232))
    d.text((int(84 * s), int(h * .36) + int(f.size * 1.05)), "read aloud · King James Version · 66 books", font=F("Literata-Italic.ttf", int(44 * s)), fill=(240, 201, 140))
    d.text((int(84 * s), int(h * .86)), "Hear it live, together, 24/7 · LiveBibleReading.com", font=F("IBMPlexSans-SemiBold.ttf", int(30 * s)), fill=(245, 241, 232))
    img.save(path, quality=92)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bible", default="bible/kjv.json")
    ap.add_argument("--about", default="bible/book-about.json")
    ap.add_argument("--index", required=True)
    ap.add_argument("--out", default="youtube-kit")
    a = ap.parse_args()
    bible, about, index = json.load(open(a.bible)), json.load(open(a.about)), json.load(open(a.index))
    os.makedirs(f"{a.out}/thumbnails", exist_ok=True); os.makedirs(f"{a.out}/descriptions", exist_ok=True)
    rows = []
    for bi, (name, chs) in enumerate(bible):
        season, ep = (1, bi + 1) if bi < 39 else (2, bi - 38)
        durs = [index[f"{bi:02d}-{c:03d}"] for c, _ in chs]
        t, starts = 0.0, []
        for d in durs: starts.append(t); t += d + PAUSE
        total = t - PAUSE
        base = f"{bi + 1:02d}-{name.replace(' ', '-')}"
        title = ("Psalms — All 150 Psalms Read Aloud | King James Bible (KJV) Audio" if bi == 18 else
                 f"{name} — The Whole Book Read Aloud | King James Bible (KJV) Audio")
        stamps = "\n".join(f"{hms(s)} {'Psalm' if bi == 18 else name} {c}" for (c, _), s in zip(chs, starts)) if len(chs) >= 3 else ""
        desc = "\n".join(x for x in [
            f"{'The Book of Psalms' if bi == 18 else 'The Book of ' + name}, read aloud from the King James Bible, chapter by chapter, with every verse on screen.",
            "",
            f"Hear the whole Bible read aloud live, 24/7, together with listeners around the world: {SITE}",
            f"Read along: {SITE}/bible/{slug(name)}-1",
            "",
            f"About {name}: {about[bi]}",
            "",
            "Chapters" if stamps else None, stamps if stamps else None, "" if stamps else None,
            f"The Whole Bible, Read Aloud · Season {season} ({'Old' if season == 1 else 'New'} Testament) · Episode {ep}.",
            "Read by a recorded digital narrator. Text: King James Version (public domain).",
            "",
            f"#Bible #KJV #AudioBible #{name.replace(' ', '')}",
        ] if x is not None)
        assert len(title) <= 100 and len(desc) <= 5000, (name, len(title), len(desc))
        open(f"{a.out}/descriptions/{base}.txt", "w").write(f"TITLE (copy into Title):\n{title}\n\nDESCRIPTION (copy into Description):\n{desc}\n")
        thumbnail(name, bi, season, ep, total, f"{a.out}/thumbnails/{base}.jpg")
        rows.append([bi + 1, name, f"Season {season}", ep, base + ".mp4", base + ".jpg", title, nice_len(total)])
    with open(f"{a.out}/episode-list.csv", "w", newline="") as f:
        w = csv.writer(f); w.writerow(["#", "Book", "Season", "Episode", "Video file", "Thumbnail", "Title", "Length"]); w.writerows(rows)
    show_art(f"{a.out}/show-artwork-16x9.jpg", 1280, 720)
    show_art(f"{a.out}/channel-banner-2560x1440.jpg", 2560, 1440)
    print(len(rows), "episodes")


if __name__ == "__main__":
    main()
