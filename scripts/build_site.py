#!/usr/bin/env python3
"""Build the clickable tree site from the folder tree.

Reads every node under tree/ (a folder's README.md, or a single .md leaf),
checks that IDs and cross-links resolve, writes site/tree.json and
site/index.html.

    pip install pyyaml
    python3 scripts/build_site.py
"""
import json
import pathlib
import re
import sys

import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent
TREE = ROOT / "tree"
SITE = ROOT / "site"
TEMPLATE = ROOT / "scripts" / "site_template.html"
SLUG = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
FM = re.compile(r"^---\n(.*?)\n---\n?(.*)$", re.S)


def node_id(md: pathlib.Path) -> str:
    rel = md.relative_to(TREE)
    parts = rel.parts[:-1] if md.name == "README.md" else rel.with_suffix("").parts
    return "/".join(parts)


def read_node(md: pathlib.Path, errors: list) -> dict:
    m = FM.match(md.read_text())
    if not m:
        errors.append(f"{md}: missing frontmatter")
        return {}
    meta = yaml.safe_load(m.group(1)) or {}
    nid = node_id(md)
    for part in nid.split("/") if nid else []:
        if not SLUG.match(part):
            errors.append(f"{md}: '{part}' is not a lowercase-hyphen slug")
    for key in ("title", "type"):
        if key not in meta:
            errors.append(f"{md}: missing '{key}'")
    core = {"title", "type", "summary", "links", "sources", "order", "status"}
    return {
        "id": nid,
        "parent": None if not nid else "/".join(nid.split("/")[:-1]),
        "title": meta.get("title", nid),
        "type": meta.get("type", "category"),
        "summary": meta.get("summary", ""),
        "status": meta.get("status", ""),
        "order": meta.get("order", 999),
        "fields": {k: str(v) for k, v in meta.items() if k not in core},
        "links": meta.get("links") or [],
        "sources": meta.get("sources") or [],
        "body": m.group(2).strip(),
        "path": str(md.relative_to(ROOT)),
        "children": [],
        "backlinks": [],
    }


def main() -> int:
    errors: list = []
    nodes = {}
    for md in sorted(TREE.rglob("*.md")):
        n = read_node(md, errors)
        if n:
            nodes[n["id"]] = n
    for n in nodes.values():
        if n["parent"] is not None:
            if n["parent"] not in nodes:
                errors.append(f"{n['path']}: parent folder has no README.md")
            else:
                nodes[n["parent"]]["children"].append(n["id"])
        for link in n["links"]:
            to = link.get("to")
            if to not in nodes:
                errors.append(f"{n['path']}: link to unknown node '{to}'")
            else:
                nodes[to]["backlinks"].append({"rel": link.get("rel", "related"), "from": n["id"]})
    for n in nodes.values():
        n["children"].sort(key=lambda c: (nodes[c]["order"], nodes[c]["title"].lower()))
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    data = json.dumps({"nodes": list(nodes.values())}, indent=1, ensure_ascii=False)
    SITE.mkdir(exist_ok=True)
    (SITE / "tree.json").write_text(data + "\n")
    html = TEMPLATE.read_text().replace("/*__TREE_DATA__*/null", data.replace("</", "<\\/"))
    (SITE / "index.html").write_text(html)
    print(f"Built {len(nodes)} nodes -> site/index.html")
    return 0


if __name__ == "__main__":
    sys.exit(main())
