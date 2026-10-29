"""Turns a checked recording into the folder the audio website serves, plus the shared 84-hour clock.

  python recorder/finish.py --bible bible/kjv.json --dir out --set kjv-onyx-1

Makes:
  audio-site/public/recordings/<set>/BB-CCC.mp3 and .json   (the recordings)
  audio-site/public/recordings/<set>/index.json             (chapter -> seconds; tells the site what exists)
  audio-site/public/recordings/<set>/clock.json             (when each chapter starts in the 84-hour week-half)
  results/<set>/index.json, clock.json                      (small copies kept in the project)

The 84 hours: each chapter's time slot = its recording + an even pause, so the slots add up to exactly 84 hours.
That keeps Genesis 1:1 at the same two moments every week (Sunday 00:00 and Wednesday 12:00 UTC).
"""
import argparse, glob, json, os, shutil, sys

TOTAL = 84 * 3600


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bible", default="bible/kjv.json")
    ap.add_argument("--dir", default="out")
    ap.add_argument("--set", required=True)
    ap.add_argument("--site", default="audio-site/public")
    a = ap.parse_args()
    bible = json.load(open(a.bible))
    keys = [f"{bi:02d}-{c:03d}" for bi, (_, chs) in enumerate(bible) for c, _ in chs]
    meta = {k: json.load(open(f"{a.dir}/{k}.json")) for k in keys}
    durs = [meta[k]["duration"] for k in keys]
    spare = TOTAL - sum(durs)
    pause = spare / len(keys)
    if pause < 1.0:
        print(f"The recording is {sum(durs) / 3600:.2f} h — too long to fit 84 h with pauses. Record again with a smaller --gap.")
        return 1
    if pause > 12.0:
        print(f"Note: {pause:.1f}s pause between chapters. A larger --gap would spread the quiet more evenly.")
    starts, t = [], 0.0
    for d in durs:
        starts.append(round(t, 3))
        t += d + pause
    clock = {"total": float(TOTAL), "chapters": starts, "source": a.set, "pause": round(pause, 3)}
    index = {k: d for k, d in zip(keys, durs)}
    dst = f"{a.site}/recordings/{a.set}"
    os.makedirs(dst, exist_ok=True)
    for k in keys:
        shutil.copy(f"{a.dir}/{k}.mp3", f"{dst}/{k}.mp3")
        m = meta[k]
        json.dump({"book": m["book"], "chapter": m["chapter"], "duration": m["duration"], "verses": m["verses"]},
                  open(f"{dst}/{k}.json", "w"), separators=(",", ":"))
    for folder in (dst, f"results/{a.set}"):
        os.makedirs(folder, exist_ok=True)
        json.dump(index, open(f"{folder}/index.json", "w"), separators=(",", ":"))
        json.dump(clock, open(f"{folder}/clock.json", "w"), separators=(",", ":"))
    print(f"{len(keys)} chapters, {sum(durs) / 3600:.2f} h of reading + {pause:.1f}s pause after each chapter = 84 h")
    return 0


if __name__ == "__main__":
    sys.exit(main())
