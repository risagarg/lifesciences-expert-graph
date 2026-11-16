"""Shared helpers for the crawler: paths, sources, name handling."""
import hashlib
import json
import pathlib
import re
import unicodedata

import yaml

ROOT = pathlib.Path(__file__).resolve().parents[2]
CRAWL = ROOT / "crawl"
RAW = CRAWL / "raw"            # downloaded pages (not committed; uploaded as a GitHub Actions artifact)
EXTRACTED = CRAWL / "extracted"  # people found on each source (committed)
USER_AGENT = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36 "
              "lifesciences-expert-graph-crawler/0.1 (+https://github.com/risagarg/lifesciences-expert-graph)")

FM = re.compile(r"^---\n(.*?)\n---", re.S)


def frontmatter(path):
    m = FM.match(path.read_text())
    return yaml.safe_load(m.group(1)) if m else {}


def sources(only=None):
    """Every page to crawl. Each evidence node's `sources` URLs, plus crawl/extra_sources.yml."""
    out = []
    for p in sorted((ROOT / "tree" / "evidence").rglob("*.md")):
        m = frontmatter(p)
        if m.get("type") != "evidence":
            continue
        node = str(p.relative_to(ROOT / "tree").with_suffix(""))
        for s in m.get("sources") or []:
            out.append({"node": node, "kind": m.get("kind", ""), "title": s.get("title", ""), "url": s["url"]})
    extra = CRAWL / "extra_sources.yml"
    if extra.exists():
        for s in yaml.safe_load(extra.read_text()) or []:
            out.append({"node": s.get("node", ""), "kind": s.get("kind", ""), "title": s.get("title", ""), "url": s["url"]})
    if only:
        out = [s for s in out if any(o in s["node"] or o in s["url"] for o in only)]
    return out


def source_id(url):
    return hashlib.sha256(url.encode()).hexdigest()[:12]


def slug(node):
    return node.replace("/", "__") or "unassigned"


def read_json(path, default=None):
    return json.loads(path.read_text()) if path.exists() else default


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")


# ---------- names ----------

PARTICLES = {"de", "da", "del", "della", "van", "von", "der", "den", "di", "le", "la", "du", "dos", "bin", "al"}


def fold(s):
    """Lowercase, strip accents and punctuation: 'Julián Panés' -> 'julian panes'."""
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(c for c in s if not unicodedata.combining(c)).lower()
    s = re.sub(r"\(.*?\)", " ", s)        # drop nicknames in parentheses
    s = re.sub(r"[^a-z\s'-]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def name_key(name):
    """(first, last, middles). Hyphens count as spaces, so 'Stein-Gold' and 'Stein Gold' compare equal."""
    words = [w.strip("'") for w in fold(name).replace("-", " ").split() if w.strip("'")]
    if len(words) < 2:
        return None
    middles = tuple(w for w in words[1:-1] if w not in PARTICLES)
    return words[0], words[-1], middles


NICKNAMES = {
    "dan": "daniel", "danny": "daniel", "ted": "edward", "ed": "edward", "bob": "robert", "rob": "robert",
    "bill": "william", "will": "william", "jim": "james", "jimmy": "james", "joe": "joseph", "ken": "kenneth",
    "steve": "steven", "mike": "michael", "tom": "thomas", "lisa": "elizabeth", "liz": "elizabeth", "beth": "elizabeth",
    "kate": "katherine", "katie": "katherine", "chris": "christopher", "rick": "richard", "rich": "richard",
    "dick": "richard", "jen": "jennifer", "jenny": "jennifer", "andy": "andrew", "drew": "andrew", "tony": "anthony",
    "larry": "lawrence", "matt": "matthew", "dave": "david", "alex": "alexander", "sam": "samuel", "ben": "benjamin",
    "nick": "nicholas", "pat": "patrick", "greg": "gregory", "jeff": "jeffrey", "tim": "timothy", "jon": "jonathan",
    "sue": "susan", "peggy": "margaret", "meg": "margaret", "maggie": "margaret", "al": "alan", "fred": "frederick",
}


def _first_ok(a, b):
    a, b = NICKNAMES.get(a, a), NICKNAMES.get(b, b)
    return a == b or (len(a) == 1 and b.startswith(a)) or (len(b) == 1 and a.startswith(b))


def same_person(a, b):
    """Conservative match between two names.

    - Last names must be equal (hyphens and spaces ignored) and first names compatible:
      'L.' matches 'Linda', 'Dan' matches 'Daniel', accents ignored.
    - Middle initials are ignored ('Linda F. Stein Gold' = 'Linda Stein Gold'), but full middle
      words must agree when both names have them.
    - A full middle word on one side blocks a match with an initial-only first name on the other:
      'L. Gold' does not match 'Linda Stein Gold', since 'Stein' may be part of the surname.
    """
    ka, kb = name_key(a), name_key(b)
    if not ka or not kb or ka[1] != kb[1] or not _first_ok(ka[0], kb[0]):
        return False
    full_a = [m for m in ka[2] if len(m) > 1]
    full_b = [m for m in kb[2] if len(m) > 1]
    if full_a and full_b:
        return set(full_a) <= set(full_b) or set(full_b) <= set(full_a)
    if (full_a and len(kb[0]) == 1) or (full_b and len(ka[0]) == 1):
        return False
    init_a = [m for m in ka[2] if len(m) == 1]
    init_b = [m for m in kb[2] if len(m) == 1]
    if init_a and init_b and init_a[0] != init_b[0]:   # 'Wei A. Wang' vs 'Wei B. Wang'
        return False
    return True
