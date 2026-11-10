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
                      "children": [], "out": [], "back": [], "people": collections.Counter(), "direct": {}}
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


RECORD_LABEL = {"clinicaltrials": "ClinicalTrials.gov", "pubmed": "PubMed", "partd": "Medicare Part D"}


def reason_text(e, ev):
    bits = [e.get("role") or "linked"]
    if e.get("detail"):
        bits.append(str(e["detail"]))
    if e.get("author_position"):
        bits.append(f"author {e['author_position']}")
    return f"{', '.join(bits)} · {ev['title']}"


def record_text(r):
    what = r.get("role") or (f"{r['papers']} papers" if r.get("papers") else "") or (f"{r['claims']} claims" if r.get("claims") else "")
    return f"{RECORD_LABEL.get(r['source'], r['source'])} {r['id']}" + (f" · {what}" if what else "")


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
            covers = e.get("covers") or [to for rel, to in nodes[ev]["out"] if rel == "covers"]
            for c in covers:
                if c not in nodes:
                    errors.append(f"people/{p['file'].name}: evidence covers unknown node '{c}'")
            covers = [c for c in covers if c in nodes]
            reason = reason_text(e, nodes[ev])
            # direct: the evidence node and each topic it covers. rolled up: their ancestors.
            for t in {ev, *covers}:
                nodes[t]["direct"].setdefault(p["id"], []).append(reason)
            targets = {ev, *covers}
            for t in list(targets):
                targets.update(ancestors(nodes, t))
            for t in targets:
                nodes[t]["people"][p["id"]] += 1
            for c in covers:
                p["topics"][c] += 1
        for r in p["records"]:
            cov = r.get("covers")
            if cov not in nodes:
                errors.append(f"people/{p['file'].name}: record covers unknown node '{cov}'")
                continue
            for t in [cov] + ancestors(nodes, cov):
                nodes[t]["people"][p["id"]] += 1
            nodes[cov]["direct"].setdefault(p["id"], []).append(record_text(r))
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
    if n["direct"]:
        direct = sorted(n["direct"].items(), key=lambda kv: (-len(kv[1]), people[kv[0]]["name"].lower()))
        out.append(f"### Experts on {n['title']} ({len(direct)})")
        out.append("Why each person is listed:\n")
        for pid, reasons in direct:
            out.append(f"- **{link(f, people[pid]['file'], people[pid]['name'])}** — " + "; ".join(reasons))
    below = {pid: c for pid, c in n["people"].items() if pid not in n["direct"]}
    if below:
        ranked = sorted(below.items(), key=lambda kv: (-kv[1], people[kv[0]]["name"].lower()))
        out.append(f"### Experts in sub-branches ({len(ranked)})")
        top = ranked[:15]
        out.append(", ".join(f"{link(f, people[pid]['file'], people[pid]['name'])} ({cnt})" for pid, cnt in top))
        more = f" …and {len(ranked) - len(top)} more." if len(ranked) > len(top) else ""
        out.append(f"\nNumbers are evidence items in this branch.{more} Open a sub-branch to see why each person is listed, or see {link(f, ROOT / 'EXPERTS.md', 'all experts')}.")
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
                det = f", {e['detail']}" if e.get("detail") else ""
                out.append(f"- {link(f, ev['file'], ev['title'])} — {e.get('role', '')}{det}{pos}")
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
    byid = {d["id"]: d for d in data}
    for n in nodes.values():
        for pid, reasons in sorted(n["direct"].items(), key=lambda kv: (-len(kv[1]), people[kv[0]]["name"].lower())):
            p, leaf = people[pid], f"{n['id']}::{pid}"
            others = sorted(t for t, nn in nodes.items() if pid in nn["direct"] and t != n["id"])
            data.append({"id": leaf, "parent": n["id"], "title": p["name"], "type": "person", "summary": "", "status": "",
                         "order": 10000, "fields": {"affiliation": p["affiliations"][-1]["text"]} if p["affiliations"] else {},
                         "links": [{"rel": "also expert in", "to": t} for t in others], "sources": [],
                         "body": "### Why listed here\n" + "\n".join(f"- {r}" for r in reasons),
                         "path": str(p["file"].relative_to(ROOT)), "children": [], "backlinks": []})
            byid[n["id"]]["children"].append(leaf)
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
