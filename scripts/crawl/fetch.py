#!/usr/bin/env python3
"""Download every source page politely and keep a dated copy.

- Checks robots.txt and skips pages it disallows.
- One request per second per site, 3 tries, and a User-Agent that says who we are.
- If a page fails or comes back nearly empty (content built by JavaScript, or a bot wall),
  tries again in a real browser with Playwright, when it's installed.
- Saves each page to crawl/raw/<id>.<html|pdf> with crawl/raw/<id>.json describing it.
- Skips pages fetched in the last 7 days unless --force.

    python3 scripts/crawl/fetch.py [--force] [node-or-url-fragment ...]
"""
import datetime
import os
import re
import sys
import time
import urllib.parse
import urllib.robotparser

import requests

from util import RAW, USER_AGENT, read_json, source_id, sources, write_json

LAST_HIT = {}
ROBOTS = {}


def allowed(url):
    host = urllib.parse.urlsplit(url)
    base = f"{host.scheme}://{host.netloc}"
    if base not in ROBOTS:
        rp = urllib.robotparser.RobotFileParser()
        try:
            r = requests.get(base + "/robots.txt", headers={"User-Agent": USER_AGENT}, timeout=20)
            rp.parse(r.text.splitlines() if r.status_code == 200 else [])
        except requests.RequestException:
            rp.parse([])
        ROBOTS[base] = rp
    return ROBOTS[base].can_fetch(USER_AGENT, url)


def polite_wait(url):
    host = urllib.parse.urlsplit(url).netloc
    gap = time.time() - LAST_HIT.get(host, 0)
    if gap < 1.0:
        time.sleep(1.0 - gap)
    LAST_HIT[host] = time.time()


def http_get(url):
    err = ""
    for attempt in range(3):
        polite_wait(url)
        try:
            r = requests.get(url, headers={"User-Agent": USER_AGENT, "Accept-Language": "en"}, timeout=60)
            if r.status_code in (429, 500, 502, 503, 504):
                time.sleep(5 * (attempt + 1))
                continue
            return r.status_code, r.headers.get("content-type", ""), r.content
        except requests.RequestException as e:
            err = str(e)
            time.sleep(5 * (attempt + 1))
    return 0, "", err.encode()


def browser_get(url):
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return None
    try:
        with sync_playwright() as p:
            b = p.chromium.launch()
            page = b.new_page(user_agent=USER_AGENT)
            # Sites with live chat or analytics never go fully quiet, so wait for the page itself,
            # then give scripts a few seconds to fill it in.
            resp = page.goto(url, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(6000)
            try:
                page.wait_for_load_state("networkidle", timeout=10000)
            except Exception:  # noqa: BLE001 - still busy is fine, we have the content
                pass
            html = page.content()
            b.close()
            return (resp.status if resp else 0), "text/html", html.encode()
    except Exception as e:  # noqa: BLE001 - any browser failure just means no fallback
        print(f"  browser failed: {e}", file=sys.stderr)
        return None


PUBMED = re.compile(r"pubmed\.ncbi\.nlm\.nih\.gov/(\d+)")
EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"


def pubmed_get(pmid):
    """PubMed's website blocks bots, so read the record from its official API and write the
    authors as plain lines extract.py understands: 'Author 1 of 12: Name | Affiliation'."""
    import xml.etree.ElementTree as ET
    polite_wait(EUTILS)
    params = {"db": "pubmed", "id": pmid, "retmode": "xml", "tool": "lifesciences-expert-graph"}
    if os.environ.get("NCBI_API_KEY"):
        params["api_key"] = os.environ["NCBI_API_KEY"]
    r = requests.get(EUTILS, params=params, headers={"User-Agent": USER_AGENT}, timeout=60)
    if r.status_code != 200:
        return r.status_code, "", b""
    art = ET.fromstring(r.content).find(".//PubmedArticle")
    if art is None:
        return 404, "", b""
    title = "".join(art.find(".//ArticleTitle").itertext()) if art.find(".//ArticleTitle") is not None else ""
    authors = [a for a in art.findall(".//AuthorList/Author") if a.findtext("LastName")]
    lines = [f"PMID {pmid}: {title}"]
    for i, a in enumerate(authors, 1):
        name = f"{a.findtext('ForeName') or a.findtext('Initials') or ''} {a.findtext('LastName')}".strip()
        aff = a.findtext(".//AffiliationInfo/Affiliation") or ""
        lines.append(f"Author {i} of {len(authors)}: {name}" + (f" | {aff}" if aff else ""))
    return 200, "text/plain", "\n".join(lines).encode()


def looks_empty(ctype, body):
    if "text/plain" in ctype:
        return len(body) < 50
    if "pdf" in ctype:
        return len(body) < 2000
    text = body.decode("utf-8", "ignore").lower()
    return len(body) < 3000 or "enable javascript" in text or "just a moment" in text or "captcha" in text


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    force = "--force" in sys.argv
    RAW.mkdir(parents=True, exist_ok=True)
    now = datetime.datetime.now(datetime.timezone.utc)
    for s in sources(args):
        sid = source_id(s["url"])
        meta_path = RAW / f"{sid}.json"
        old = read_json(meta_path, {})
        if old.get("ok") and not force:
            age = now - datetime.datetime.fromisoformat(old["fetched_at"])
            if age.days < 7:
                continue
        if not PUBMED.search(s["url"]) and not allowed(s["url"]):  # PubMed goes through its official API
            write_json(meta_path, {**s, "id": sid, "ok": False, "error": "disallowed by robots.txt",
                                   "fetched_at": now.isoformat()})
            print(f"robots.txt disallows {s['url']}", file=sys.stderr)
            continue
        pm = PUBMED.search(s["url"])
        if pm:
            status, ctype, body = pubmed_get(pm.group(1))
            method = "pubmed-api"
        else:
            status, ctype, body = http_get(s["url"])
            method = "http"
        if method == "http" and (status != 200 or looks_empty(ctype, body)):
            got = browser_get(s["url"]) if "pdf" not in ctype and not s["url"].lower().endswith(".pdf") else None
            if got and got[0] == 200 and not looks_empty(got[1], got[2]):
                status, ctype, body = got
                method = "browser"
        ok = status == 200 and not looks_empty(ctype, body)
        ext = "txt" if "text/plain" in ctype else "pdf" if ("pdf" in ctype or body[:4] == b"%PDF") else "html"
        if ok:
            (RAW / f"{sid}.{ext}").write_bytes(body)
        write_json(meta_path, {**s, "id": sid, "ok": ok, "status": status, "content_type": ctype, "ext": ext,
                               "method": method, "bytes": len(body), "fetched_at": now.isoformat()})
        print(f"{'ok ' if ok else 'FAIL'} {status} {method:7} {s['url'][:100]}", file=sys.stderr)


if __name__ == "__main__":
    main()
