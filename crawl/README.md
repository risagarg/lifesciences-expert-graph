# Crawler

Reads web pages and PDFs (conference programs, news write-ups, FDA rosters, leadership pages) and finds the people named on them, with the exact quote each one came from.

**Status: test version.** It only writes a report. Nothing it finds is added to `people/` yet.

## How it works

It's one crawler for every site, not one per site. Each run does four steps:

| Step | Script | What it does |
|---|---|---|
| 1. Sources | `scripts/crawl/util.py` | Takes every URL listed in an evidence node's `sources`, plus anything in [`extra_sources.yml`](extra_sources.yml) |
| 2. Fetch | `scripts/crawl/fetch.py` | Downloads each page politely: checks robots.txt, one request per second per site, retries. Falls back to a real browser when a page is built by JavaScript. Keeps a dated copy |
| 3. Find people | `scripts/crawl/extract.py` | Turns the page or PDF into text, then finds people two ways (below). Every person keeps the quote they came from |
| 4. Score | `scripts/crawl/evaluate.py` | Compares what it found with the people we entered by hand for that evidence node, and writes [`report.md`](report.md) |

**Finding people, two layers:**
1. **Rules** (always on, free): spots patterns like "Jane Doe, MD, PhD" and "Dr. Jane Doe", the institution after the name, and a role from nearby words ("presented", "chair", "panel", "faculty").
2. **AI** (only if an `ANTHROPIC_API_KEY` secret is set in the repo): reads the page and returns each person with role, affiliation and topic. It must copy a quote from the page for every person, and the code throws out anyone whose quote isn't really on the page. That check is what keeps it from making people up.

**Matching names** is deliberately strict:
- "Stein-Gold" matches "Stein Gold", "L." matches "Linda", and accents are ignored.
- "L. Gold" does *not* match "Linda Stein Gold", and "W. Wang" never matches "Y. Wang".

## Run it

**On GitHub (recommended, since most sites are reachable from there):** Actions tab > **crawl** > **Run workflow**. You can type part of a node name (e.g. `maui-derm`) to crawl just one source. When it finishes, `crawl/report.md` is updated and the downloaded pages are attached to the run as a download.

**On your computer:**

```bash
pip3 install -r requirements-crawl.txt
python3 -m playwright install chromium     # optional: for JavaScript-heavy pages
python3 scripts/crawl/fetch.py
python3 scripts/crawl/extract.py
python3 scripts/crawl/evaluate.py
open crawl/report.md
```

`python3 scripts/crawl/selftest.py` checks the extractor and name matching offline.

## Reading the report

- **Hand-entered found:** how many of the people we added by hand for that source the crawler found again. This is the main quality number.
- **Missed:** people it should have found. Use these to fix the extractor.
- **New candidates:** people it found that aren't linked to that node. Usually not mistakes: by hand we only added people relevant to the diseases in the tree. These are what a reviewer would check before adding.
- **LLM answers dropped:** answers the AI gave whose quote wasn't on the page, so they were thrown out.

## Add a source

Add the URL to the `sources` of its evidence node (preferred), or to [`extra_sources.yml`](extra_sources.yml) if there's no node for it yet. No code needed. A source only needs its own parser if it's huge and the general extractor keeps missing people on it.

## Next steps

1. Run it on GitHub and read the first report.
2. Fix what it misses.
3. Then let it add **new candidates** to `people/`, marked *auto, not reviewed*, the same way the data pull does.
