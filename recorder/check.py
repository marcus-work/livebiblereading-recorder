"""Checks a finished recording before it goes online. Stops (exit code 1) on any problem.

  python recorder/check.py --bible bible/kjv.json --dir out            # the whole Bible must be there
  python recorder/check.py --bible bible/kjv.json --dir out --partial  # only check what's there

Checks, for every chapter:
  - its .mp3 and .json both exist (and nothing extra or doubled)
  - the number of verses in the recording matches the Bible text, in order, with times that only go forward
  - the mp3 plays from start to end without errors, and its length matches the timing file
  - no silence longer than 3 seconds inside the chapter (a sign of a glitch)
  - every verse is a sensible length for its words (catches cut-off or garbled verses)
"""
import argparse, glob, json, os, re, subprocess, sys
from concurrent.futures import ThreadPoolExecutor

SANE = (0.03, 0.14)          # seconds per character, per verse
MAX_QUIET = 3.0


def probe(mp3):
    """Decode the whole file; return (problems, decoded seconds, longest silence)."""
    r = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-v", "info", "-xerror", "-i", mp3,
                        "-af", "silencedetect=noise=-50dB:d=2", "-f", "null", "-"], capture_output=True, text=True)
    log = r.stderr
    errs = [l for l in log.splitlines() if re.search(r"error|invalid|corrupt", l, re.I) and "silence" not in l]
    m = re.findall(r"time=(\d+):(\d+):([\d.]+)", log)
    secs = (lambda h, mi, s: int(h) * 3600 + int(mi) * 60 + float(s))(*m[-1]) if m else 0.0
    quiet = [float(x) for x in re.findall(r"silence_duration: ([\d.]+)", log)]
    if r.returncode != 0:
        errs.append(f"ffmpeg exit {r.returncode}")
    return errs, secs, max(quiet, default=0.0)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bible", default="bible/kjv.json")
    ap.add_argument("--dir", default="out")
    ap.add_argument("--partial", action="store_true")
    ap.add_argument("--report", default="")
    a = ap.parse_args()
    bible = json.load(open(a.bible))
    want = {f"{bi:02d}-{c:03d}": (bi, c, vs) for bi, (_, chs) in enumerate(bible) for c, vs in chs}
    have_json = {os.path.basename(p)[:-5] for p in glob.glob(f"{a.dir}/??-???.json")}
    have_mp3 = {os.path.basename(p)[:-4] for p in glob.glob(f"{a.dir}/??-???.mp3")}
    problems, notes = [], []
    if not a.partial:
        for k in sorted(set(want) - have_json):
            problems.append(f"{k}: missing")
    for k in sorted((have_json | have_mp3) - set(want)):
        problems.append(f"{k}: not a chapter of this Bible")
    for k in sorted(have_json ^ have_mp3):
        problems.append(f"{k}: has only one of .mp3 / .json")
    keys = sorted(have_json & have_mp3 & set(want))

    def one(k):
        bi, c, vs = want[k]
        out = []
        m = json.load(open(f"{a.dir}/{k}.json"))
        if (m.get("book"), m.get("chapter")) != (bi, c):
            out.append(f"{k}: timing file is labelled {m.get('book')}-{m.get('chapter')}")
        got = [v for v, _ in m["verses"]]
        if got != [v for v, _ in vs]:
            out.append(f"{k}: verses {got[:3]}… do not match the text ({len(got)} vs {len(vs)})")
        ts = [t for _, t in m["verses"]]
        if any(b <= a_ for a_, b in zip(ts, ts[1:])) or (ts and ts[-1] >= m["duration"]):
            out.append(f"{k}: verse times out of order")
        for (v, text), L in zip(vs, m.get("lengths", [])):
            r = L / max(1, len(text))
            if len(text) >= 25 and not SANE[0] <= r <= SANE[1]:
                out.append(f"{k}:{v}: verse is {L:.1f}s for {len(text)} letters — sounds cut off or garbled")
        errs, secs, quiet = probe(f"{a.dir}/{k}.mp3")
        out += [f"{k}: audio error: {e}" for e in errs[:3]]
        if abs(secs - m["duration"]) > 0.6:
            out.append(f"{k}: audio is {secs:.1f}s but timing file says {m['duration']:.1f}s")
        if quiet > MAX_QUIET:
            out.append(f"{k}: {quiet:.1f}s of silence inside the chapter")
        return out, m["duration"], m.get("retried", 0)

    total = retried = 0.0
    with ThreadPoolExecutor(os.cpu_count() or 2) as ex:
        for out, d, r in ex.map(one, keys):
            problems += out
            total += d
            retried += r
    notes.append(f"{len(keys)} of {len(want)} chapters checked, {total / 3600:.2f} hours of audio, {int(retried)} verses re-recorded in pieces")
    text = "\n".join(["## Recording check", "", *notes, "",
                      f"**{len(problems)} problem(s)**" if problems else "**All good.**", *[f"- {p}" for p in problems[:300]]])
    print(text)
    if a.report:
        open(a.report, "w").write(text + "\n")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
