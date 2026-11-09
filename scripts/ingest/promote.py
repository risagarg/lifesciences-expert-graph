#!/usr/bin/env python3
"""Turn the top candidates in data/ into files in people/.

For each indication and source, takes the top N people, merges them into an
existing person when an ORCID or NPI matches (or the full first and last name
match), and otherwise creates a new person file marked `status: auto`.
Each addition is stored as a `records:` entry with its source and ID.
    python3 scripts/ingest/promote.py [--top 25] [slug ...]
"""
import argparse
import collections
import re

import yaml

from common import DATA, ROOT, indications, read_csv, slugify

PEOPLE = ROOT / "people"
FM = re.compile(r"^---\n(.*?)\n---\n(.*)$", re.S)
DEGREES = re.compile(r",.*$|\b(MD|PhD|DO|MBBS|MSc|MS|MPH|FRCPC|FAAD|Prof\.?|Dr\.?)\b\.?", re.I)


def load_people():
    out = {}
    for md in PEOPLE.glob("*.md"):
        m = FM.match(md.read_text())
        out[md.stem] = {"meta": yaml.safe_load(m.group(1)), "rest": m.group(2), "path": md}
    return out


def full_key(name):
    parts = DEGREES.sub("", name).replace(".", " ").split()
    return (parts[0].lower(), parts[-1].lower()) if len(parts) >= 2 else None


def find(people, name, orcid="", npi=""):
    for slug, p in people.items():
        m = p["meta"]
        if (orcid and m.get("orcid") == orcid) or (npi and str(m.get("npi")) == npi):
            return slug
    k = full_key(name)
    for slug, p in people.items():
        if k and full_key(p["meta"]["name"]) == k:
            return slug
    return None


def upsert(people, name, record, orcid="", npi="", affiliation=""):
    name = re.sub(r"\s+", " ", DEGREES.sub("", name)).strip(" ,")
    slug = find(people, name, orcid, npi)
    if not slug:
        slug = slugify(name)
        while slug in people:
            slug += "-2"
        people[slug] = {"meta": {"name": name, "type": "person", "status": "auto"}, "rest": "", "path": PEOPLE / f"{slug}.md"}
    m = people[slug]["meta"]
    if orcid and not m.get("orcid"):
        m["orcid"] = orcid
    if npi and not m.get("npi"):
        m["npi"] = npi
    if affiliation:
        affs = m.setdefault("affiliations", [])
        if not any(a.get("text") == affiliation for a in affs):
            affs.append({"text": affiliation, "as_of": record.get("year", "unknown"), "source": record["source"]})
    recs = m.setdefault("records", [])
    if not any(r["source"] == record["source"] and r["id"] == record["id"] for r in recs):
        recs.append(record)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--top", type=int, default=25)
    ap.add_argument("slugs", nargs="*")
    args = ap.parse_args()
    people = load_people()
    for ind in indications(args.slugs):
        node, s = ind["node"], ind["slug"]
        # ClinicalTrials.gov: officials ranked by number of trials
        trials = collections.defaultdict(list)
        for r in read_csv(DATA / "clinicaltrials" / f"{s}.csv"):
            trials[r["official_name"]].append(r)
        for name, rs in sorted(trials.items(), key=lambda kv: -len(kv[1]))[: args.top]:
            if len(rs) < 2:
                break
            for r in rs:
                upsert(people, name, {"source": "clinicaltrials", "id": r["nct_id"], "role": r["official_role"],
                                      "covers": node, "year": (r["start_date"] or "")[:4],
                                      "url": f"https://clinicaltrials.gov/study/{r['nct_id']}"},
                       affiliation=rs[0]["official_affiliation"])
        # PubMed: authors ranked by paper count
        for r in read_csv(DATA / "pubmed" / f"{s}.csv")[: args.top]:
            if int(r["papers"]) < 3:
                break
            upsert(people, r["name"], {"source": "pubmed", "id": f"{s}:{r['author_key']}", "covers": node,
                                       "papers": int(r["papers"]), "pmids": r["pmids"], "year": r["latest_year"]},
                   orcid=r["orcid"], affiliation=r["latest_affiliation"])
        # Part D: prescribers ranked by claims
        for r in read_csv(DATA / "partd" / f"{s}.csv")[: args.top]:
            upsert(people, f"{r['first_name']} {r['last_name']}".title(),
                   {"source": "partd", "id": f"{r['data_year']}:{r['npi']}:{s}", "covers": node,
                    "claims": int(r["total_claims"]), "drugs": r["drugs"], "year": r["data_year"],
                    "practice": f"{r['city']}, {r['state']}"}, npi=r["npi"])
    for slug, p in people.items():
        head = yaml.safe_dump(p["meta"], sort_keys=False, allow_unicode=True, width=1000)
        p["path"].write_text(f"---\n{head}---\n{p['rest']}")
    print(f"{len(people)} people on disk")


if __name__ == "__main__":
    main()
