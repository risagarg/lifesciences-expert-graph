"""Shared helpers for the ingest scripts. Standard library plus PyYAML only."""
import csv
import json
import pathlib
import re
import sys
import time
import unicodedata
import urllib.parse
import urllib.request

import yaml

ROOT = pathlib.Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
UA = "lifesciences-expert-graph/0.1 (research; contact via repo owner)"


def indications(only=None):
    items = yaml.safe_load((ROOT / "ingest" / "indications.yml").read_text())
    return [i for i in items if not only or i["slug"] in only]


def get(url, params=None, as_json=True, tries=4, pause=0.0):
    if params:
        url += ("&" if "?" in url else "?") + urllib.parse.urlencode(params, doseq=True)
    for attempt in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=90) as r:
                body = r.read().decode("utf-8")
            if pause:
                time.sleep(pause)
            return json.loads(body) if as_json else body
        except Exception as e:  # network or HTTP error: back off and retry
            if attempt == tries - 1:
                raise RuntimeError(f"GET failed after {tries} tries: {url}: {e}") from e
            time.sleep(2 ** attempt)


def write_csv(path, rows, fields):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    print(f"wrote {len(rows)} rows -> {path.relative_to(ROOT)}", file=sys.stderr)


def read_csv(path):
    if not path.exists():
        return []
    with path.open() as f:
        return list(csv.DictReader(f))


def name_key(last, first):
    """Surname plus first initial, accent-folded. Used only as a weak match key."""
    fold = lambda s: unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()
    last = re.sub(r"[^a-z-]", "", fold(last))
    first = re.sub(r"[^a-z]", "", fold(first))[:1]
    return f"{last}|{first}"


def slugify(s):
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")


NOT_A_PERSON = re.compile(
    r"\b(director|clinical|trials?|medical|study|call|center|centre|inc|llc|ltd|gmbh|pharma\w*|"
    r"therapeutics|biosciences?|sciences|corporation|company|department|hospital|university|"
    r"research|investigator|sponsor|transparency|monitor|team|services|group)\b", re.I)


def is_person_name(name):
    """True for something that looks like a person's name, not a role or company placeholder."""
    if not name:
        return False
    core = re.sub(r",.*$", "", name).strip()
    words = core.replace(".", " ").split()
    return 2 <= len(words) <= 6 and not NOT_A_PERSON.search(core) and not any(c.isdigit() for c in core)


def clean_name(name):
    """Drop degrees and titles: 'Jane Q. Doe, MD, PhD' -> 'Jane Q. Doe'."""
    name = re.sub(r",.*$", "", name or "")
    name = re.sub(r"\b(Prof|Professor|Dr|Mr|Mrs|Ms)\b\.?\s*", "", name, flags=re.I)
    name = re.sub(r"\b(MD|PhD|DO|MBBS|MSc|MS|MPH|FRCPC|FAAD|MBChB|FRCP)\b\.?", "", name)
    return re.sub(r"\s+", " ", name).strip(" ,")


FM = re.compile(r"^---\n(.*?)\n---\n(.*)$", re.S)


def read_person(path):
    m = FM.match(path.read_text())
    return yaml.safe_load(m.group(1)), m.group(2)


def write_person(path, meta, rest):
    head = yaml.safe_dump(meta, sort_keys=False, allow_unicode=True, width=1000)
    path.write_text(f"---\n{head}---\n{rest}")
