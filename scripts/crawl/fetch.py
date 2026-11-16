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
            resp = page.goto(url, wait_until="networkidle", timeout=60000)
            html = page.content()
            b.close()
            return (resp.status if resp else 0), "text/html", html.encode()
    except Exception as e:  # noqa: BLE001 - any browser failure just means no fallback
        print(f"  browser failed: {e}", file=sys.stderr)
        return None


def looks_empty(ctype, body):
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
        if not allowed(s["url"]):
            write_json(meta_path, {**s, "id": sid, "ok": False, "error": "disallowed by robots.txt",
                                   "fetched_at": now.isoformat()})
            print(f"robots.txt disallows {s['url']}", file=sys.stderr)
            continue
        status, ctype, body = http_get(s["url"])
        method = "http"
        if status != 200 or looks_empty(ctype, body):
            got = browser_get(s["url"]) if "pdf" not in ctype and not s["url"].lower().endswith(".pdf") else None
            if got and got[0] == 200 and not looks_empty(got[1], got[2]):
                status, ctype, body = got
                method = "browser"
        ok = status == 200 and not looks_empty(ctype, body)
        ext = "pdf" if ("pdf" in ctype or body[:4] == b"%PDF") else "html"
        if ok:
            (RAW / f"{sid}.{ext}").write_bytes(body)
        write_json(meta_path, {**s, "id": sid, "ok": ok, "status": status, "content_type": ctype, "ext": ext,
                               "method": method, "bytes": len(body), "fetched_at": now.isoformat()})
        print(f"{'ok ' if ok else 'FAIL'} {status} {method:7} {s['url'][:100]}", file=sys.stderr)


if __name__ == "__main__":
    main()
