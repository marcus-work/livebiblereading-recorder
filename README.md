# Live Bible Reading — recorder

Records the whole Bible in one voice, checks every chapter, backs it up, and publishes it to
**livebiblereading.com/recordings/** for the website's 24/7 reading. One button.

## Run it
1. **Actions** tab → **Record the Bible** → **Run workflow** → green **Run workflow** button.
2. Wait about 2–3 hours. GitHub emails you when it's finished (or if something failed).
3. The summary page shows the check report and the web address of the new recording.

Leave the boxes as they are for the King James Version in the Onyx voice. To try a few chapters first,
type e.g. `0:1,18:23` (Genesis 1 and Psalm 23) in the test box — that records them and checks them but
publishes nothing.

## Rules that keep it safe
- **A new recording always gets a new folder name** (`kjv-onyx-1`, then `kjv-onyx-2`, …). The website keeps
  using the old one until it's switched over, so it never breaks mid-update.
- Nothing is published unless every chapter passes the checks (see `recorder/check.py`).
- Every recording is also backed up under **Releases** (one zip per book).
- File names are book and chapter numbers: `00-001` = Genesis 1 … `65-022` = Revelation 22.

## What's where
| Path | What it is |
|---|---|
| `bible/` | Bible texts (same files the website shows) |
| `recorder/render.py` | records chapters (the work is split into 40 parts that run at the same time) |
| `recorder/pronounce.json` | names the voice says wrong, with the right sounds |
| `recorder/check.py` | the checks every chapter must pass |
| `recorder/finish.py` | builds the audio folder and the exact 84-hour clock |
| `audio-site/` | the audio website (Cloudflare, files only, serves `/recordings/*`) |
| `results/<folder>/` | small copies of the clock, index and check report for each recording |

## The one secret it needs
`CLOUDFLARE_API_TOKEN` (Settings → Secrets and variables → Actions). A Cloudflare token made with the
**Edit Cloudflare Workers** template, for your account and the livebiblereading.com zone.

Voice: Kokoro-82M (Apache-2.0). Text: King James Version (public domain).
