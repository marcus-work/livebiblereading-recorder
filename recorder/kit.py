"""YouTube show kit: thumbnails, show artwork, titles, descriptions with chapter timestamps, upload guide.

  python recorder/kit.py --index results/kjv-onyx-1/index.json --out youtube-kit
"""
import argparse, csv, json, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from key_passages import KEY
from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
F = lambda name, size: ImageFont.truetype(os.path.join(HERE, "fonts", name), size)
PAUSE = 2.0
W, H = 1280, 720
SITE = "https://livebiblereading.com"
COFFEE = "https://buymeacoffee.com/livebiblereading"
CHANNEL = "https://www.youtube.com/@LiveBibleReadingCom"
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


def guide_titles(bi):
    import glob
    f = glob.glob(os.path.join(HERE, "guide", f"{bi:02d}-*.json"))
    return json.load(open(f[0]))["titles"] if f else {}


def thumbnail(name, bi, season, ep, length, path, guided=False):
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
    d.text((80, 590), f"KING JAMES VERSION  ·  BOOK {bi + 1} OF 66", font=small, fill=ink)
    tag = nice_len(length)
    tw = d.textlength(tag, font=small)
    d.rounded_rectangle([W - 110 - tw, 580, W - 70, 640], radius=12, fill=(0, 0, 0))
    d.text((W - 90 - tw, 590), tag, font=small, fill=(255, 255, 255))
    if guided:
        g = F("IBMPlexSans-SemiBold.ttf", 30); gw = d.textlength("GUIDED", font=g)
        d.rounded_rectangle([W - 110 - gw, 60, W - 70, 112], radius=10, fill=(240, 201, 140))
        d.text((W - 90 - gw, 68), "GUIDED", font=g, fill=(26, 18, 8))
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
    ap.add_argument("--guided", default="", help="folder with the guided videos' .json timings: makes the Guided kit")
    a = ap.parse_args()
    bible, about, index = json.load(open(a.bible)), json.load(open(a.about)), json.load(open(a.index))
    os.makedirs(f"{a.out}/thumbnails", exist_ok=True); os.makedirs(f"{a.out}/descriptions", exist_ok=True)
    rows = []
    for bi, (name, chs) in enumerate(bible):
        season, ep = (1, bi + 1) if bi < 39 else (2, bi - 38)
        base = f"{bi + 1:02d}-{name.replace(' ', '-')}"
        if a.guided:
            gj = json.load(open(f"{a.guided}/{base}.json"))
            starts, total = [s_ for _, s_ in gj["chapters"]], gj["total"]
        else:
            durs = [index[f"{bi:02d}-{c:03d}"] for c, _ in chs]
            t, starts = 0.0, []
            for d in durs: starts.append(t); t += d + PAUSE
            total = t - PAUSE
        bk = "Psalms" if bi == 18 else name
        title = ("Psalms – All 150 Psalms Read Aloud | KJV Audio Bible with Text" if bi == 18 else
                 f"{name} – Full Book Read Aloud | KJV Audio Bible with Text")
        if a.guided:
            title = ("Psalms – KJV Audio Bible with Text | Guided, All 150 Psalms" if bi == 18 else
                     f"{name} – KJV Audio Bible with Text | Guided Full Book Read Aloud")
        cname = lambda c: f"Psalm {c}" if bi == 18 else f"{name} {c}"
        stamps = "\n".join(f"{hms(s)} {cname(c)}" for (c, _), s in zip(chs, starts)) if len(chs) >= 3 else ""
        if a.guided:
            gtitles = guide_titles(bi)
            stamps = "0:00 Introduction\n" + "\n".join(f"{hms(s)} {cname(c)}" + (f": {gtitles[str(c)]}" if gtitles.get(str(c)) else "") for (c, _), s in zip(chs, starts))
        at = {c: s for (c, _), s in zip(chs, starts)}
        keys = [f"{hms(at[c])} {cname(c)}: {label}" for c, label in sorted(KEY.get(bi, [])) if c in at and (len(chs) >= 3 or a.guided)]
        nxt = bible[bi + 1][0] if bi + 1 < len(bible) else ""
        testament = "Old Testament" if season == 1 else "New Testament"
        desc = "\n".join(x for x in [
            (f"The complete Book of {bk}, read aloud from the King James Bible (KJV), with a short introduction, a title for every chapter, and old words explained on screen. Book {bi + 1} of 66 in the Guided Audio Bible, from Genesis to Revelation, in order."
             if a.guided else
             f"The complete Book of {bk}, read aloud from the King James Bible (KJV), with every verse on screen. Book {bi + 1} of 66 in The Whole Bible, Read Aloud, from Genesis to Revelation, in order."),
            "",
            f"▶ Hear the whole Bible read aloud LIVE, 24/7, with listeners around the world (free, no ads, no sign-up): {SITE}",
            f"📖 Read along, chapter by chapter: {SITE}/bible/{slug(name)}-1",
            f"🌙 Falling asleep or driving? Sleep mode and car mode are on the website.",
            f"☕ This reading is free for everyone. Help keep it on the air: {COFFEE}",
            f"🔔 Subscribe for the whole Bible, in order: {CHANNEL}?sub_confirmation=1",
            f"🌎 En español: {SITE}/es/",
            "",
            f"About {bk}: {about[bi]}",
            "",
            "Well-known passages" if keys else None, "\n".join(keys) if keys else None, "" if keys else None,
            "Chapters" if stamps else None, stamps if stamps else None, "" if stamps else None,
            f"Next in this series: {nxt}." if nxt else "This is the last book of the Bible. Start again from Genesis in the playlist.",
            f"{'The Guided Audio Bible' if a.guided else 'The Whole Bible, Read Aloud'} · {testament} · Book {bi + 1} of 66.",
            "Text: King James Version (public domain). Spot a mistake? Tell us on the website: Suggest an idea.",
            "",
            f"#AudioBible #KJV #{bk.replace(' ', '')}",
        ] if x is not None)
        if len(desc) > 5000 and a.guided:      # long books: chapter titles make it too long, so list chapters plainly
            plain = "0:00 Introduction\n" + "\n".join(f"{hms(s_)} {cname(c)}" for (c, _), s_ in zip(chs, starts))
            desc = desc.replace(stamps, plain)
        tags = ", ".join(dict.fromkeys([f"{bk} audio bible", f"book of {bk}", f"{bk} KJV", f"{bk} read aloud", f"{bk} full book",
                         "audio bible", "KJV audio bible", "King James Bible"] + (["Bible explained", "guided Bible reading"] if a.guided else []) + [ "Bible read aloud", "Bible audiobook", "whole Bible", "scripture", "Bible for sleep"]))
        assert len(title) <= 100 and len(desc) <= 5000 and len(tags) <= 480, (name, len(title), len(desc), len(tags))
        open(f"{a.out}/descriptions/{base}.txt", "w").write(f"TITLE (copy into Title):\n{title}\n\nDESCRIPTION (copy into Description):\n{desc}\n\nTAGS (Show more > Tags):\n{tags}\n\nPLAYLISTS: The Whole Bible, Read Aloud (KJV) + {testament}\n")
        thumbnail(name, bi, season, ep, total, f"{a.out}/thumbnails/{base}.jpg", guided=bool(a.guided))
        rows.append([bi + 1, name, f"Season {season}", ep, base + ".mp4", base + ".jpg", title, nice_len(total)])
    with open(f"{a.out}/episode-list.csv", "w", newline="") as f:
        w = csv.writer(f); w.writerow(["#", "Book", "Season", "Episode", "Video file", "Thumbnail", "Title", "Length"]); w.writerows(rows)
    open(f"{a.out}/PINNED-COMMENT.txt", "w").write(
        "Post this as the first comment on every video, then tap the three dots next to it and choose Pin.\n\n"
        "🙏 Thank you for listening. The whole Bible is also read aloud LIVE, 24/7, at " + SITE + " : everyone hears the same verse at the same moment, "
        "with sleep mode and car mode, free and with no ads on the website. If it blesses you, you can help keep it on the air here: " + COFFEE + "\n\n"
        "🔔 Subscribe to hear the whole Bible, book by book, in order.\n\n"
        "Which verse spoke to you today? Share it below. 👇\n")
    show_art(f"{a.out}/show-artwork-16x9.jpg", 1280, 720)
    show_art(f"{a.out}/channel-banner-2560x1440.jpg", 2560, 1440)
    print(len(rows), "episodes")


if __name__ == "__main__":
    main()
