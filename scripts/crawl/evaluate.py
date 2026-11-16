#!/usr/bin/env python3
"""Score the crawler against the people we already entered by hand.

For each evidence node, the answer key is every person in people/ whose evidence
points at that node. We check:
  - found:  how many of the hand-entered people the crawler also found (recall)
  - missed: hand-entered people it didn't find (to debug the extractor)
  - new:    people it found that aren't linked to that node. Not necessarily wrong:
            by hand we only added people relevant to the diseases in the tree.
            These are the candidates a reviewer would check.
Writes crawl/report.md.

    python3 scripts/crawl/evaluate.py
"""
import collections

import re

from util import CRAWL, EXTRACTED, RAW, ROOT, fold, frontmatter, name_key, read_json, same_person, source_id


def page_texts(data):
    """Text of each fetched page for this node, if the raw copies are here (they are on GitHub runs)."""
    from extract import page_text
    out = []
    for s in data["sources"]:
        meta = read_json(RAW / f"{source_id(s['url'])}.json")
        if meta and meta.get("ok") and (RAW / f"{meta['id']}.{meta['ext']}").exists():
            out.append(page_text(meta))
    return out


def near(texts, name):
    """Where a missed person's last name appears on the page, to tell 'not on the page' from 'misread'."""
    k = name_key(name)
    if not k:
        return None
    for text in texts:
        flat = re.sub(r"\s+", " ", text)
        m = re.search(rf"(?i)\b{re.escape(k[1])}\b", fold(flat).replace("-", " "))
        if m:
            return flat[max(0, m.start() - 70):m.end() + 70].strip()
    return ""

def load_people():
    people = []
    for p in sorted((ROOT / "people").glob("*.md")):
        m = frontmatter(p)
        names = [m.get("name", "")] + list(m.get("aliases") or [])
        nodes = {e.get("node") for e in m.get("evidence") or []}
        people.append({"slug": p.stem, "name": m.get("name", ""), "names": names, "nodes": nodes})
    return people


def matches(found_name, person):
    return any(same_person(found_name, n) for n in person["names"] if n)


def main():
    people = load_people()
    rows, detail = [], []
    tot = collections.Counter()
    for f in sorted(EXTRACTED.glob("*.json")):
        data = read_json(f)
        node = data["node"]
        key = [p for p in people if node in p["nodes"]]
        found = [x for s in data["sources"] for x in s["people"]]
        ok = sum(1 for s in data["sources"] if s["ok"])
        dropped = sum(s.get("llm_dropped_ungrounded", 0) for s in data["sources"])
        hit = [p for p in key if any(matches(x["name"], p) for x in found)]
        missed = [p for p in key if p not in hit]
        new, elsewhere = [], []
        seen = set()
        for x in found:
            if any(matches(x["name"], p) for p in key) or x["name"] in seen:
                continue
            seen.add(x["name"])
            other = next((p for p in people if matches(x["name"], p)), None)
            (elsewhere if other else new).append((x, other))
        recall = f"{len(hit)}/{len(key)}" if key else "–"
        rows.append(f"| {node.split('/')[-1]} | {ok}/{len(data['sources'])} | {recall} | {len(new)} | {len(elsewhere)} | {dropped} |")
        if ok:
            tot["key"] += len(key); tot["hit"] += len(hit)
        tot["new"] += len(new); tot["src_ok"] += ok; tot["src"] += len(data["sources"])
        d = [f"### {node}", ""]
        for s in data["sources"]:
            state = f"ok ({s['method']}, {s.get('chars', 0):,} chars)" if s["ok"] else f"not fetched (status {s['status']}) {s.get('error', '')}"
            d.append(f"- [{s['title'] or s['url']}]({s['url']}): {state}, {len(s['people'])} people")
        if missed:
            texts = page_texts(data)
            d += ["", "**Missed** (entered by hand, not found by the crawler):", ""]
            for p in missed:
                ctx = near(texts, p["name"]) if texts else None
                where = ("page text not available here" if ctx is None else
                         "name not on the page" if ctx == "" else f"on the page as: “…{ctx.replace('|', '/')}…”")
                d.append(f"- {p['name']}: {where}")
        if new:
            d += ["", "**New candidates** (found, not in the graph):", ""]
            for x, _ in new[:40]:
                q = x["quotes"][0].replace("|", "/").replace("\n", " ")
                d.append(f"- **{x['name']}**{', ' + x['credentials'] if x.get('credentials') else ''}"
                         f" · {x['role']}{' · ' + x['affiliation'] if x.get('affiliation') else ''}"
                         f" · {'+'.join(x['methods'])} · “{q[:220]}”")
            if len(new) > 40:
                d.append(f"- …and {len(new) - 40} more in `crawl/extracted/{f.name}`")
        if elsewhere:
            d += ["", "**Already in the graph under other evidence:** " + ", ".join(
                f"{x['name']} → [{o['name']}](../people/{o['slug']}.md)" for x, o in elsewhere)]
        detail += d + [""]
    rate = f"{tot['hit']}/{tot['key']} ({100 * tot['hit'] / tot['key']:.0f}%)" if tot["key"] else "–"
    out = ["# Crawler test report", "",
           "Generated by `scripts/crawl/evaluate.py`. The crawler re-reads the sources behind each evidence node "
           "and is scored against the people we entered by hand. Nothing here is added to the graph.", "",
           f"- **Pages fetched:** {tot['src_ok']}/{tot['src']}",
           f"- **Hand-entered people found again:** {rate} (only counting nodes whose pages were fetched)",
           f"- **New candidates to review:** {tot['new']}", "",
           "| Evidence | Pages fetched | Hand-entered found | New candidates | In graph elsewhere | LLM answers dropped (quote not on page) |",
           "|---|---|---|---|---|---|", *rows, "", "## Detail", "", *detail]
    (CRAWL / "report.md").write_text("\n".join(out) + "\n")
    print(f"found {rate} hand-entered; {tot['new']} new candidates; pages {tot['src_ok']}/{tot['src']}")


if __name__ == "__main__":
    main()
