#!/usr/bin/env python3
"""Find the people named on each downloaded page.

One generic extractor for every site, in two layers:

1. Rules (always on, free): finds "Name, MD/PhD/..." and "Dr. Name" patterns, the
   affiliation after them, and a role from nearby words (presented, chair, panel...).
2. LLM (only if ANTHROPIC_API_KEY is set): reads the page and returns each person with
   role, affiliation and topic. Every person must come with a quote copied from the page,
   and the code drops anyone whose quote isn't really on the page.

Every result keeps the exact quote it came from. Output: crawl/extracted/<node>.json

    python3 scripts/crawl/extract.py [node-or-url-fragment ...]
"""
import io
import json
import os
import re
import sys
import urllib.request

from util import EXTRACTED, RAW, fold, name_key, read_json, slug, sources, source_id, write_json

# ---------- page -> text ----------


def page_text(meta):
    path = RAW / f"{meta['id']}.{meta['ext']}"
    data = path.read_bytes()
    if meta["ext"] == "txt":
        return data.decode("utf-8")
    if meta["ext"] == "pdf":
        from pypdf import PdfReader
        return "\n".join((pg.extract_text() or "") for pg in PdfReader(io.BytesIO(data)).pages)
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(data, "lxml")
    for tag in soup(["script", "style", "noscript", "nav", "footer", "header", "form", "aside", "svg"]):
        tag.decompose()
    text = soup.get_text("\n")
    return re.sub(r"\n\s*\n+", "\n", text)


# ---------- layer 1: rules ----------

DEG_LIST = ("M.D.|MD|D.O.|DO|Ph.D.|PhD|MPH|MSc|MS|MA|MBBS|MBChB|FRCPC|FRCP|FAAD|FACP|FACR|FACG|AGAF|FACE|FTOS|"
            "DABOM|MSCE|MHS|MBA|PharmD|DNP|NP|PA-C|RN|MMSc|FRACP|FRCPI|DPhil|JD|MSW|MSN|EdD|BCPS|BCPP|RPh|MPhil|CNSC|"
            "DrPH|BSN|MHA|MSPH|FASGE|FAASLD|FRCSC|MBE|MD-PhD|M.D|Ph.D")
DEG = "(?:" + "|".join(re.escape(d) + (r"(?![A-Za-z])") for d in DEG_LIST.split("|")) + ")"
NOT_DEG = r"(?!(?:" + "|".join(re.escape(d) for d in DEG_LIST.split("|")) + r")(?![A-Za-z]))"
WORD = rf"{NOT_DEG}[A-ZÀ-Ý][A-Za-zÀ-ÿ'’\-]+"
NAME = rf"((?:{WORD}|[A-Z]\.)(?:\s+(?:{WORD}|[A-Z]\.|de|van|von|da|del|der|di|le|la|dos)){{1,4}})"
WITH_DEG = re.compile(rf"{NAME},?\s+(?P<deg>{DEG}(?:\s*,?\s*{DEG})*)")
DR = re.compile(rf"\bDr\.?\s+{NAME}")
ORG_WORDS = re.compile(r"University|Universit|Hospital|Medical|Center|Centre|Clinic|Institute|School|College|Health|"
                       r"Foundation|Pharma|Laborator|Research|Inc\b|LLC|Society|Association|Department|Faculty|FDA", re.I)
NOT_NAME = re.compile(r"\b(University|Hospital|Center|Centre|Clinic|Institute|School|College|Department|Session|"
                      r"Symposium|Congress|Meeting|Conference|Committee|Phase|Trial|Study|Program|Award|Lecture|"
                      r"Professor|Director|Chair|Medicine|Dermatology|Rheumatology|Gastroenterology|Health|The|And|"
                      r"For|With|New|Update|Annual|Late|Breaking|Abstract|Poster|Moderator|Speaker|Faculty|Panel|"
                      r"January|February|March|April|May|June|July|August|September|October|November|December|"
                      r"Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)\b")
ROLE_WORDS = [("presenter", r"present(ed|s|ing|er)|late[- ]breaker|oral presentation"),
              ("chair", r"\bchair(ed|man|woman|s)?\b|moderat(or|ed)|co-?director"),
              ("panelist", r"\bpanel(ist|ists)?\b"),
              ("author", r"first author|lead author|et al\.?"),
              ("speaker", r"\bspeak(er|ers|s)\b|faculty|lecture"),
              ("member", r"\bmember\b|roster|term")]


def guess_role(context):
    for role, pat in ROLE_WORDS:
        if re.search(pat, context, re.I):
            return role
    return "named"


TITLE_WORDS = {"councilor", "member", "board", "president", "chair", "chairs", "professor", "prof", "director",
               "relationships", "patient", "dr", "ceo", "officer", "vice", "executive", "chief", "founder",
               "investigator", "lead", "senior", "associate", "assistant", "fellow", "editor", "session", "by",
               "moderator", "faculty", "speaker", "speakers", "panelist", "panelists", "author", "authors",
               "presenter", "co-chair", "cochair", "dean", "head", "emeritus", "resident", "attending"}
PARTICLE_END = {"de", "van", "von", "da", "del", "der", "di", "le", "la", "dos"}


def clean(name):
    """Tidy a matched name: drop job titles or headline words in front, acronyms, and trailing particles."""
    name = re.sub(r"\s+", " ", name.replace("’", "'")).strip(" ,.")
    name = re.sub(r"(?<![\w'])([A-Z])(?![\w.'])", r"\1.", name)   # 'Bruce E Strober' -> 'Bruce E. Strober'
    toks = name.split()
    cut = 0
    for i, w in enumerate(toks[:-2]):  # keep at least two words for the name itself
        acronym = 2 <= len(w) <= 5 and w.isupper() and not w.endswith(".") and not toks[i + 1].isupper()   # 'IPC Board Member ...'
        if w.lower().strip(".,") in TITLE_WORDS or acronym:
            cut = i + 1
    toks = toks[cut:]
    while toks and toks[-1].lower() in PARTICLE_END:
        toks = toks[:-1]
    return " ".join(toks)


def rule_people(text):
    lines = text.split("\n")
    found = []
    for i, line in enumerate(lines):
        line = line.strip()
        if not line:
            continue
        ctx = " ".join(lines[max(0, i - 1):i + 2])
        prev_role = guess_role(lines[i - 1]) if i else "named"
        for rx, has_deg in ((WITH_DEG, True), (DR, False)):
            for m in rx.finditer(line):
                name = clean(m.group(1))
                if NOT_NAME.search(name) or not name_key(name):
                    continue
                if not has_deg and len(name.split()) < 2:
                    continue
                after = line[m.end():m.end() + 200]
                aff = ""
                am = re.match(r"\s*[,(\-–—]\s*([^;()\n]{6,160})", after)
                if am and ORG_WORDS.search(am.group(1)):
                    aff = am.group(1).strip(" ,.)")
                elif i + 1 < len(lines) and ORG_WORDS.search(lines[i + 1]) and len(lines[i + 1].strip()) < 160:
                    aff = lines[i + 1].strip(" ,.")
                start = max(0, m.start() - 120)
                # role: words in the same clause first, then the same line, then a heading on the line above
                before = re.split(r"[.;]\s|\s{3,}", line[:m.start()])[-1]
                after = re.split(r"[.;]\s", line[m.end():])[0][:120]
                role = guess_role(before)
                if role == "named":
                    role = guess_role(after)
                if role == "named":
                    role = guess_role(re.sub(re.escape(m.group(0)), " ", line))
                    if role == "named" and line.strip() == m.group(0).strip():  # name alone on its line
                        role = prev_role if prev_role != "named" else "named"
                found.append({"name": name, "credentials": (m.group("deg") if has_deg else ""),
                              "affiliation": aff, "role": role, "topic": "",
                              "quote": line[start:m.end() + 160].strip(), "method": "rules"})
    return found


AUTHOR_LABEL = re.compile(r"\b(authors?|by|faculty|speakers?|panel(ists)?|presenters?|investigators?|members?)\b", re.I)
SHORT = re.compile(r"^((?:[A-ZÀ-Ý][a-zà-ÿ'’\-]+\s){0,2}[A-ZÀ-Ý][a-zà-ÿ'’\-]+)\s+([A-Z]{1,3})$")  # 'Stein Gold L', 'Strober BE'
LAST_FIRST = re.compile(rf"^([A-ZÀ-Ý][A-Za-zà-ÿ'’\- ]+),\s+((?:{WORD}|[A-Z]\.?)(?:\s*(?:{WORD}|[A-Z]\.?))*)$")
FIRST_LAST = re.compile(rf"^((?:{WORD}|[A-Z]\.)(?:\s+(?:{WORD}|[A-Z]\.|de|van|von|da|del|der|di)){{1,3}})$")


def author_list_people(text):
    """Plain author lists without degrees:
    'Menter A, Strober BE, Kaplan DH' (PubMed style), 'Menter, Alan; Strober, Bruce E.', or
    'Alan Menter, Bruce E. Strober, Daniel H. Kaplan' when the line or the one above says authors/faculty/by."""
    lines = text.split("\n")
    found = []
    for i, line in enumerate(lines):
        line = line.strip()
        if line.count(",") + line.count(";") < 2 or len(line) > 4000:
            continue
        labelled = bool(AUTHOR_LABEL.search(line[:40])) or (i > 0 and bool(AUTHOR_LABEL.search(lines[i - 1][-60:])))
        body = re.sub(r"^\s*[A-Za-z ]{0,25}:\s*", "", line)  # drop a leading 'Authors:' label
        body = re.sub(r"\s*(et al\.?|and others)\s*\.?$", "", body)
        for sep, kind in ((";", "last_first"), (",", "short"), (",", "first_last")):
            items = [x.strip(" .*†‡§0-9") for x in re.split(rf"{sep}|\band\b|&", body) if x.strip(" .*†‡§0-9")]
            if len(items) < 3:
                continue
            names = []
            for it in items:
                it = re.sub(r"\s*\d+(,\d+)*$", "", it)  # superscript affiliation numbers
                if kind == "short" and (m := SHORT.match(it)):
                    names.append(" ".join(c + "." for c in m.group(2)) + " " + m.group(1))
                elif kind == "last_first" and (m := LAST_FIRST.match(it)):
                    names.append(f"{m.group(2)} {m.group(1)}")
                elif kind == "first_last" and labelled and (m := FIRST_LAST.match(it)):
                    names.append(m.group(1))
            if len(names) >= 3 and len(names) >= 0.7 * len(items):
                for k, n in enumerate(names):
                    n = clean(n)
                    if NOT_NAME.search(n) or not name_key(n):
                        continue
                    found.append({"name": n, "credentials": "", "affiliation": "",
                                  "role": "first author" if k == 0 else "author", "topic": "",
                                  "quote": line[:300], "method": "rules"})
                break
    return found


PUBMED_LINE = re.compile(r"^Author (\d+) of \d+: (.+?)(?: \| (.+))?$")


def pubmed_people(text):
    """Lines written by fetch.py's PubMed adapter: 'Author 1 of 12: Linda Stein Gold | Henry Ford Health'."""
    out = []
    for line in text.split("\n"):
        m = PUBMED_LINE.match(line.strip())
        if m and name_key(m.group(2)):
            out.append({"name": m.group(2), "credentials": "", "affiliation": (m.group(3) or "")[:200],
                        "role": "first author" if m.group(1) == "1" else "author", "topic": "",
                        "quote": line.strip()[:300], "method": "rules"})
    return out


# ---------- layer 2: LLM ----------

PROMPT = """You are extracting named experts from one web page or PDF for an expert database.
The page is: {title} ({url}). It is evidence of type "{kind}".

Return ONLY a JSON array. One object per real, named person who is shown as taking part
(presenting, chairing, speaking, authoring, serving on the committee, leading the organization).
Skip people only mentioned in passing (e.g. a patient story, a journalist byline).

Fields: "name" (as written, without degrees), "credentials", "affiliation" (as written, or ""),
"role" (one of: presenter, chair, panelist, speaker, author, first author, member, leader, quoted, named),
"topic" (talk/trial/drug in a few words, or ""),
"quote" (an EXACT, continuous excerpt of the page text, at most 300 characters, that contains the
person's name and shows their role; copy it character for character).

Do not guess. If a field isn't on the page, use "". Page text:
<<<
{text}
>>>"""


def llm_people(text, src):
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        return []
    model = os.environ.get("CRAWL_MODEL", "claude-sonnet-5-5")
    out, size = [], 14000
    for start in range(0, len(text), size - 1000):  # overlapping chunks
        chunk = text[start:start + size]
        body = json.dumps({"model": model, "max_tokens": 8000, "messages": [
            {"role": "user", "content": PROMPT.format(text=chunk, **src)}]}).encode()
        req = urllib.request.Request("https://api.anthropic.com/v1/messages", data=body, headers={
            "x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=300) as r:
                reply = json.loads(r.read())["content"][0]["text"]
            arr = json.loads(reply[reply.find("["):reply.rfind("]") + 1])
        except Exception as e:  # noqa: BLE001 - a failed chunk is reported, not fatal
            print(f"  LLM chunk failed: {e}", file=sys.stderr)
            continue
        for p in arr:
            if isinstance(p, dict) and p.get("name"):
                out.append({k: str(p.get(k, "") or "") for k in ("name", "credentials", "affiliation", "role", "topic", "quote")}
                           | {"method": "llm"})
    return out


def squash(s):
    return re.sub(r"\s+", " ", fold(s)).strip()


def grounded(p, page):
    """The quote must really be on the page, and must contain the person's last name."""
    q = squash(p["quote"])
    k = name_key(p["name"])
    return bool(q) and q in page and k is not None and k[1][:5] in q.replace(" ", "").replace("-", "")


# ---------- combine ----------


def merge(people):
    out = {}
    for p in people:
        k = name_key(p["name"])
        if not k:
            continue
        key = (k[1], k[0])
        cur = out.get(key)
        if not cur:
            out[key] = {**p, "methods": [p["method"]], "quotes": [p["quote"]]}
            continue
        for f in ("credentials", "affiliation", "topic"):
            if not cur.get(f) and p.get(f):
                cur[f] = p[f]
        if cur.get("role") in ("named", "") and p.get("role") not in ("named", ""):
            cur["role"] = p["role"]
        if p["method"] not in cur["methods"]:
            cur["methods"].append(p["method"])
        if p["quote"] not in cur["quotes"] and len(cur["quotes"]) < 3:
            cur["quotes"].append(p["quote"])
    for v in out.values():
        v.pop("method", None)
        v.pop("quote", None)
    return sorted(out.values(), key=lambda p: name_key(p["name"])[1])


def main():
    only = [a for a in sys.argv[1:] if not a.startswith("--")]
    by_node = {}
    for s in sources(only):
        meta = read_json(RAW / f"{source_id(s['url'])}.json")
        entry = {"url": s["url"], "title": s["title"], "ok": bool(meta and meta.get("ok")),
                 "status": (meta or {}).get("status"), "method": (meta or {}).get("method"),
                 "error": (meta or {}).get("error", ""), "people": []}
        if entry["ok"]:
            text = page_text(meta)
            page = squash(text)
            found = rule_people(text) + author_list_people(text) + pubmed_people(text)
            cap = int(os.environ.get("CRAWL_LLM_MAX_CHARS", "120000"))  # huge PDFs: the AI reads the start only
            llm = llm_people(text[:cap], s)
            kept = [p for p in llm if grounded(p, page)]
            entry["llm_dropped_ungrounded"] = len(llm) - len(kept)
            entry["chars"] = len(text)
            entry["people"] = merge(found + kept)
        by_node.setdefault(s["node"], {"node": s["node"], "kind": s["kind"], "sources": []})["sources"].append(entry)
        n = len(entry["people"])
        print(f"{'ok ' if entry['ok'] else 'skip'} {n:3} people  {s['url'][:90]}", file=sys.stderr)
    for node, data in by_node.items():
        write_json(EXTRACTED / f"{slug(node)}.json", data)


if __name__ == "__main__":
    main()
