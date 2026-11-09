#!/usr/bin/env python3
"""Validate the tree and people, then write link indexes for GitHub browsing.

    pip install -r requirements.txt
    python3 scripts/build.py          # check + regenerate indexes
    python3 scripts/build.py --check  # check only, fail if indexes are stale
    python3 scripts/build.py --site   # also build site/index.html (local viewer)

Everything between the GENERATED marker and the end of a file is rewritten on
each run. Edit only the frontmatter and the text above the marker.
"""
import collections
import json
import os
import pathlib
import re
import sys

import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent
TREE, PEOPLE = ROOT / "tree", ROOT / "people"
MARK = "<!-- GENERATED: edit above this line; run python3 scripts/build.py -->"
SLUG = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
FM = re.compile(r"^---\n(.*?)\n---\n?(.*)$", re.S)
TYPE_LABEL = {"root": "Root", "category": "Category", "stakeholder": "Stakeholder", "disease": "Disease",
              "mechanism": "Mechanism", "asset": "Drug", "data-source": "Data source",
              "organization": "Organization", "evidence": "Evidence", "person": "Person"}


def split(text):
    m = FM.match(text)
    if not m:
        return None, None
    body = m.group(2).split(MARK)[0].strip()
    return yaml.safe_load(m.group(1)) or {}, body


def load(errors):
    nodes = {}
    for md in sorted(TREE.rglob("*.md")):
        rel = md.relative_to(TREE)
        parts = rel.parts[:-1] if md.name == "README.md" else rel.with_suffix("").parts
        nid = "/".join(parts)
        meta, body = split(md.read_text())
        if meta is None:
            errors.append(f"{md.relative_to(ROOT)}: missing frontmatter")
            continue
        for p in parts:
            if not SLUG.match(p):
                errors.append(f"{md.relative_to(ROOT)}: '{p}' is not a lowercase-hyphen name")
        for key in ("title", "type"):
            if key not in meta:
                errors.append(f"{md.relative_to(ROOT)}: missing '{key}'")
        nodes[nid] = {"id": nid, "file": md, "meta": meta, "body": body,
                      "parent": None if not parts else "/".join(parts[:-1]),
                      "title": meta.get("title", nid), "type": meta.get("type", "category"),
                      "children": [], "out": [], "back": [], "people": collections.Counter()}
    people = {}
    for md in sorted(PEOPLE.glob("*.md")):
        meta, body = split(md.read_text())
        pid = "people/" + md.stem
        if meta is None or "name" not in meta:
            errors.append(f"people/{md.name}: needs frontmatter with 'name'")
            continue
        if not SLUG.match(md.stem):
            errors.append(f"people/{md.name}: file name must be lowercase-hyphen")
        people[pid] = {"id": pid, "file": md, "meta": meta, "body": body, "name": meta["name"],
                       "evidence": meta.get("evidence") or [], "records": meta.get("records") or [], "affiliations": meta.get("affiliations") or [],
                       "topics": collections.Counter()}
    return nodes, people


def link(frm: pathlib.Path, to: pathlib.Path, text: str) -> str:
    rel = os.path.relpath(to, frm.parent).replace(os.sep, "/")
    text = text.replace("|", "\\|").replace("[", "(").replace("]", ")")
    return f"[{text}]({rel.replace(' ', '%20')})"


def ancestors(nodes, nid):
    out, n = [], nodes.get(nid)
    while n and n["parent"] is not None:
        out.insert(0, n["parent"])
        n = nodes.get(n["parent"])
    return out


def resolve(nodes, people, errors):
    for n in nodes.values():
        if n["parent"] is not None:
            if n["parent"] in nodes:
                nodes[n["parent"]]["children"].append(n["id"])
            else:
                errors.append(f"{n['file'].relative_to(ROOT)}: parent folder has no README.md")
        for l in n["meta"].get("links") or []:
            to = l.get("to")
            if to not in nodes:
                errors.append(f"{n['file'].relative_to(ROOT)}: link to unknown node '{to}'")
                continue
            n["out"].append((l.get("rel", "related"), to))
            nodes[to]["back"].append((l.get("rel", "related"), n["id"]))
    for n in nodes.values():
        n["children"].sort(key=lambda c: (nodes[c]["meta"].get("order", 999), nodes[c]["title"].lower()))
    for p in people.values():
        for e in p["evidence"]:
            ev = e.get("node")
            if ev not in nodes:
                errors.append(f"people/{p['file'].name}: evidence node '{ev}' not found")
                continue
            # the evidence node itself, plus every topic it covers, plus their ancestors
            targets = {ev} | {to for rel, to in nodes[ev]["out"] if rel == "covers"}
            for t in list(targets):
                targets.update(ancestors(nodes, t))
            for t in targets:
                nodes[t]["people"][p["id"]] += 1
            for rel, to in nodes[ev]["out"]:
                if rel == "covers":
                    p["topics"][to] += 1
        for r in p["records"]:
            cov = r.get("covers")
            if cov not in nodes:
                errors.append(f"people/{p['file'].name}: record covers unknown node '{cov}'")
                continue
            for t in [cov] + ancestors(nodes, cov):
                nodes[t]["people"][p["id"]] += 1
            p["topics"][cov] += 1
        for a in p["affiliations"]:
            org = a.get("org")
            if org:
                if org not in nodes:
                    errors.append(f"people/{p['file'].name}: affiliation org '{org}' not found")
                else:
                    for t in [org] + ancestors(nodes, org):
                        nodes[t]["people"][p["id"]] += 1


def render_node(n, nodes, people):
    f, out = n["file"], []
    crumbs = [link(f, nodes[a]["file"], nodes[a]["title"]) for a in ancestors(nodes, n["id"])]
    if crumbs:
        out.append("**Path:** " + " / ".join(crumbs + [n["title"]]))
    if n["children"]:
        out.append(f"### Contents ({len(n['children'])})")
        for c in n["children"]:
            cn = nodes[c]
            stub = " *(stub)*" if cn["meta"].get("status") == "stub" else ""
            count = f" · {len(cn['people'])} experts" if cn["people"] else ""
            summ = f" — {cn['meta']['summary']}" if cn["meta"].get("summary") else ""
            out.append(f"- {link(f, cn['file'], cn['title'])}{stub}{count}{summ}")
    if n["out"] or n["back"]:
        out.append("### Connections")
        for rel, to in n["out"]:
            out.append(f"- {rel.replace('_', ' ')} → {link(f, nodes[to]['file'], nodes[to]['title'])}")
        for rel, frm in n["back"]:
            out.append(f"- ← {rel.replace('_', ' ')} · {link(f, nodes[frm]['file'], nodes[frm]['title'])}")
    if n["people"]:
        ranked = sorted(n["people"].items(), key=lambda kv: (-kv[1], people[kv[0]]["name"].lower()))
        out.append(f"### Experts ({len(ranked)})")
        top = ranked[:20]
        out.append(", ".join(f"{link(f, people[pid]['file'], people[pid]['name'])} ({cnt})" for pid, cnt in top))
        if len(ranked) > len(top):
            out.append(f"\n…and {len(ranked) - len(top)} more in {link(f, ROOT / 'EXPERTS.md', 'all experts')}. Numbers are linked evidence items under this node.")
        else:
            out.append("\nNumbers are linked evidence items under this node.")
    srcs = n["meta"].get("sources") or []
    if srcs:
        out.append("### Sources")
        out += [f"- [{s.get('title', s['url'])}]({s['url']})" for s in srcs]
    return out


def render_person(p, nodes):
    f, out = p["file"], ["**Path:** [All experts](../EXPERTS.md) / " + p["name"]]
    if p["topics"]:
        out.append("### Expertise")
        for t, c in sorted(p["topics"].items(), key=lambda kv: (-kv[1], nodes[kv[0]]["title"])):
            out.append(f"- {link(f, nodes[t]['file'], nodes[t]['title'])} ({c})")
    if p["evidence"]:
        out.append("### Evidence")
        for e in p["evidence"]:
            ev = nodes.get(e.get("node"))
            if ev:
                pos = f", author {e['author_position']}" if e.get("author_position") else ""
                out.append(f"- {link(f, ev['file'], ev['title'])} — {e.get('role', '')}{pos}")
    if p["records"]:
        out.append(f"### Data records ({len(p['records'])})")
        labels = {"clinicaltrials": "ClinicalTrials.gov", "pubmed": "PubMed", "partd": "Medicare Part D"}
        for r in p["records"][:50]:
            what = r.get("role") or (f"{r['papers']} papers" if r.get("papers") else "") or (f"{r['claims']} claims" if r.get("claims") else "")
            ref = f"[{r['id']}]({r['url']})" if r.get("url") else r["id"]
            cov = nodes[r["covers"]]
            out.append(f"- {labels.get(r['source'], r['source'])} {ref} — {what} · {link(f, cov['file'], cov['title'])}")
        if len(p["records"]) > 50:
            out.append(f"- …and {len(p['records']) - 50} more in the frontmatter")
    if p["affiliations"]:
        out.append("### Affiliations")
        for a in p["affiliations"]:
            org = f" → {link(f, nodes[a['org']]['file'], nodes[a['org']]['title'])}" if a.get("org") in nodes else ""
            out.append(f"- {a.get('text', '')} ({a.get('as_of', 'date unknown')}){org}")
    return out


def write(path, meta_text, body, gen, check, stale):
    content = meta_text + (("\n" + body + "\n") if body else "") + "\n" + MARK + "\n\n" + "\n".join(gen) + "\n"
    if path.read_text() != content:
        stale.append(str(path.relative_to(ROOT)))
        if not check:
            path.write_text(content)


def experts_index(nodes, people):
    rows = sorted(people.values(), key=lambda p: (-(len(p["evidence"]) + len(p["records"])), p["name"].lower()))
    out = ["# Experts", "",
           f"{len(rows)} people. Each one is linked to cited evidence in [tree/evidence](tree/evidence/README.md). "
           "Ranked by number of evidence items and data records. *(auto)* marks people added by the ingest scripts and not yet reviewed. Generated by `scripts/build.py`, so edit the files in `people/` rather than this page.", "",
           "| Expert | Evidence | Top topics | Latest affiliation in sources |", "|---|---:|---|---|"]
    for p in rows:
        top = sorted(p["topics"].items(), key=lambda kv: -kv[1])[:3]
        topics = ", ".join(link(ROOT / "EXPERTS.md", nodes[t]["file"], nodes[t]["title"]) for t, _ in top)
        aff = p["affiliations"][-1]["text"] if p["affiliations"] else "—"
        out.append(f"| {link(ROOT / 'EXPERTS.md', p['file'], p['name'])}{' *(auto)*' if p['meta'].get('status') == 'auto' else ''} | {len(p['evidence']) + len(p['records'])} | {topics} | {aff.replace('|', '/')} |")
    return "\n".join(out) + "\n"


def build_site(nodes, people):
    tmpl = ROOT / "scripts" / "site_template.html"
    data = []
    for n in nodes.values():
        m = n["meta"]
        data.append({"id": n["id"], "parent": n["parent"], "title": n["title"], "type": n["type"],
                     "summary": m.get("summary", ""), "status": m.get("status", ""), "order": m.get("order", 999),
                     "fields": {k: str(v) for k, v in m.items() if k not in {"title", "type", "summary", "links", "sources", "order", "status"}},
                     "links": [{"rel": r, "to": t} for r, t in n["out"]], "sources": m.get("sources") or [],
                     "body": n["body"], "path": str(n["file"].relative_to(ROOT)),
                     "children": list(n["children"]), "backlinks": [{"rel": r, "from": f} for r, f in n["back"]]})
    pids = sorted(people, key=lambda k: people[k]["name"].lower())
    data.append({"id": "people", "parent": "", "title": "People", "type": "category", "summary": "Named experts linked to evidence.",
                 "status": "", "order": 0, "fields": {}, "links": [], "sources": [], "body": "", "path": "people/",
                 "children": pids, "backlinks": []})
    data[[d["id"] for d in data].index("")]["children"].insert(0, "people")
    for pid in pids:
        p = people[pid]
        links = [{"rel": "authored", "to": e["node"]} for e in p["evidence"] if e.get("node") in nodes]
        data.append({"id": pid, "parent": "people", "title": p["name"], "type": "person", "summary": "", "status": "",
                     "order": 999, "fields": {"affiliation": p["affiliations"][-1]["text"]} if p["affiliations"] else {},
                     "links": links, "sources": [], "body": p["body"], "path": str(p["file"].relative_to(ROOT)),
                     "children": [], "backlinks": []})
    byid = {d["id"]: d for d in data}
    for d in data:
        for l in d["links"]:
            if d["type"] == "person":
                byid[l["to"]]["backlinks"].append({"rel": "authored", "from": d["id"]})
    blob = json.dumps({"nodes": data}, ensure_ascii=False)
    (ROOT / "site").mkdir(exist_ok=True)
    (ROOT / "site" / "index.html").write_text(tmpl.read_text().replace("/*__TREE_DATA__*/null", blob.replace("</", "<\\/")))


def main():
    check, site = "--check" in sys.argv, "--site" in sys.argv
    errors = []
    nodes, people = load(errors)
    if not errors:
        resolve(nodes, people, errors)
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    stale = []
    for n in nodes.values():
        meta_text = n["file"].read_text().split("\n---\n", 1)[0] + "\n---\n"
        write(n["file"], meta_text, n["body"], render_node(n, nodes, people), check, stale)
    for p in people.values():
        meta_text = p["file"].read_text().split("\n---\n", 1)[0] + "\n---\n"
        write(p["file"], meta_text, p["body"], render_person(p, nodes), check, stale)
    idx = ROOT / "EXPERTS.md"
    new = experts_index(nodes, people)
    if not idx.exists() or idx.read_text() != new:
        stale.append("EXPERTS.md")
        if not check:
            idx.write_text(new)
    if site:
        build_site(nodes, people)
    print(f"{len(nodes)} nodes, {len(people)} people. "
          + (f"{len(stale)} files out of date." if check else f"{len(stale)} files updated."))
    return 1 if check and stale else 0


if __name__ == "__main__":
    sys.exit(main())
