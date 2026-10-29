"""Records Bible chapters with the Kokoro voice (open source, Apache-2.0).

Every chapter becomes two files, named by book and chapter number so the order is never in doubt:
  BB-CCC.mp3   the reading (mono, 48 kbps)            e.g. 00-001 = Genesis 1, 65-022 = Revelation 22
  BB-CCC.json  where each verse starts, for the website's verse-by-verse sync

The Bible is split into equal-sized "shards" (by amount of text) so many computers can record at once.

  python recorder/render.py --bible bible/kjv.json --voice am_onyx --speed 0.88 --gap 1.35 \
         --shard 3 --shards 40 --out out
  python recorder/render.py ... --only 0:1,16:8        # just these chapters (book index : chapter)
"""
import argparse, json, os, re, subprocess, sys, time
import numpy as np
import soundfile as sf
from kokoro_onnx import Kokoro

SR = 24000
INTRO_PAUSE = 1.5      # seconds after "Genesis, chapter 2."
TAIL = 0.3             # seconds after the last verse (the website adds the pause between chapters)
# seconds of speech per character must fall in this range, otherwise the verse is re-recorded in pieces
SANE = (0.035, 0.13)


def chapters_of(bible):
    return [(bi, c, verses) for bi, (_, chs) in enumerate(bible) for c, verses in chs]


def shard_of(chs, shard, shards):
    """Split chapters, in Bible order, into `shards` runs of roughly equal text length."""
    weights = [sum(len(t) for _, t in vs) + 40 for _, _, vs in chs]
    total, out, acc, k = sum(weights), [], 0, 0
    for ch, w in zip(chs, weights):
        if acc + w / 2 > total * (k + 1) / shards and k < shards - 1:
            k += 1
        if k == shard:
            out.append(ch)
        acc += w
    return out


def spoken_book(name):
    for a, b in (("1 ", "First "), ("2 ", "Second "), ("3 ", "Third ")):
        if name.startswith(a):
            return b + name[2:]
    return name


def clean(text):
    """Text as it should be heard (the screen keeps the original)."""
    text = text.replace("æ", "ae").replace("Æ", "Ae").replace("…", "...").replace("—", ", ").replace("’", "'")
    return re.sub(r"\b([A-Z])([A-Z]+)\b", lambda m: m.group(1) + m.group(2).lower(), text)   # LORD -> Lord


class Voice:
    def __init__(self, models, voice, speed, lang, pronounce):
        self.k = Kokoro(f"{models}/kokoro-v1.0.onnx", f"{models}/voices-v1.0.bin")
        self.voice, self.speed, self.lang = voice, speed, lang
        self.fixes = []                     # (wrong phonemes, right phonemes) for names the voice gets wrong
        for word, right in pronounce.items():
            wrong = self.k.tokenizer.phonemize(word, lang).strip(" .")
            if wrong and wrong != right:
                self.fixes.append((re.compile(r"(?<!\S)" + re.escape(wrong) + r"(?=z?(?:[\s,.;:!?]|$))"), right))
        self.fixed = 0

    def say(self, text):
        ph = self.k.tokenizer.phonemize(text, self.lang)
        for pat, right in self.fixes:
            ph, n = pat.subn(right, ph)
            self.fixed += n
        a, _ = self.k.create(ph, voice=self.voice, speed=self.speed, is_phonemes=True)
        return a

    def verse(self, text):
        a = self.say(text)
        r = len(a) / SR / max(1, len(text))
        if SANE[0] <= r <= SANE[1] or len(text) < 25:
            return a, False
        # unusual length: record it again sentence by sentence, then keep whichever is closer to normal
        parts = [p for p in re.split(r"(?<=[.;:?!])\s+", text) if p.strip()]
        pause = np.zeros(int(SR * 0.25), dtype=np.float32)
        b = np.concatenate([x for p in parts for x in (self.say(p), pause)][:-1]) if len(parts) > 1 else self.say(text)
        rb = len(b) / SR / len(text)
        mid = 0.065
        return (b if abs(rb - mid) < abs(r - mid) else a), True


def render(voice, bible, bi, c, verses, gap, out):
    base = f"{out}/{bi:02d}-{c:03d}"
    name = bible[bi][0]
    intro = f"Psalm {c}." if bi == 18 else (f"The book of {spoken_book(name)}. Chapter 1." if c == 1 else f"{spoken_book(name)}, chapter {c}.")
    a = voice.say(intro)
    parts, marks, pos, retried = [a, np.zeros(int(SR * INTRO_PAUSE), dtype=np.float32)], [], 0, 0
    pos = len(a) + int(SR * INTRO_PAUSE)
    for k, (v, text) in enumerate(verses):
        a, r = voice.verse(clean(text))
        retried += r
        marks.append([v, round(pos / SR, 3), round(len(a) / SR, 3)])
        g = np.zeros(int(SR * (gap if k < len(verses) - 1 else TAIL)), dtype=np.float32)
        parts += [a.astype(np.float32), g]
        pos += len(a) + len(g)
    audio = np.concatenate(parts)
    peak = float(np.max(np.abs(audio))) or 1.0
    if peak > 0.98:
        audio = audio * (0.98 / peak)
    sf.write(base + ".wav", audio, SR)
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", base + ".wav", "-ac", "1", "-b:a", "48k", base + ".tmp.mp3"], check=True)
    os.replace(base + ".tmp.mp3", base + ".mp3")
    os.remove(base + ".wav")
    meta = {"book": bi, "chapter": c, "duration": round(pos / SR, 3), "verses": [[v, t] for v, t, _ in marks],
            "lengths": [l for _, _, l in marks], "retried": retried}
    with open(base + ".tmp.json", "w") as f:
        json.dump(meta, f, separators=(",", ":"))
    os.replace(base + ".tmp.json", base + ".json")      # the .json is written last: it marks the chapter as finished
    return pos / SR


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bible", default="bible/kjv.json")
    ap.add_argument("--voice", default="am_onyx")
    ap.add_argument("--speed", type=float, default=0.88)
    ap.add_argument("--gap", type=float, default=1.35, help="seconds of quiet between verses")
    ap.add_argument("--lang", default="en-us")
    ap.add_argument("--pronounce", default="recorder/pronounce.json")
    ap.add_argument("--models", default="models")
    ap.add_argument("--shard", type=int, default=0)
    ap.add_argument("--shards", type=int, default=1)
    ap.add_argument("--only", default="", help="e.g. 0:1,16:8 (book index:chapter)")
    ap.add_argument("--out", default="out")
    a = ap.parse_args()
    bible = json.load(open(a.bible))
    pron = json.load(open(a.pronounce)) if os.path.exists(a.pronounce) else {}
    pron = {k: v for k, v in pron.items() if not k.startswith("_")}
    chs = chapters_of(bible)
    if a.only:
        want = {tuple(map(int, x.split(":"))) for x in a.only.split(",")}
        todo = [ch for ch in chs if (ch[0], ch[1]) in want]
    else:
        todo = shard_of(chs, a.shard, a.shards)
    os.makedirs(a.out, exist_ok=True)
    if not todo:
        print("nothing to record in this part"); return 0
    voice = Voice(a.models, a.voice, a.speed, a.lang, pron)
    print(f"shard {a.shard + 1} of {a.shards}: {len(todo)} chapters, {todo[0][:2]} to {todo[-1][:2]}", flush=True)
    t0, secs = time.time(), 0.0
    for bi, c, verses in todo:
        if os.path.exists(f"{a.out}/{bi:02d}-{c:03d}.json"):
            continue                                      # already done (a re-run picks up where it stopped)
        t1 = time.time()
        d = render(voice, bible, bi, c, verses, a.gap, a.out)
        secs += d
        print(f"{bible[bi][0]} {c}: {d / 60:.1f} min of audio in {time.time() - t1:.0f}s", flush=True)
    print(f"done: {secs / 3600:.2f} h of audio in {(time.time() - t0) / 3600:.2f} h; {voice.fixed} name fixes", flush=True)


if __name__ == "__main__":
    sys.exit(main())
