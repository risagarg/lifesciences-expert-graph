#!/usr/bin/env python3
"""Look up NPIs for people in people/ who don't have one yet, via the NPI Registry API.

Only accepts a match when exactly one individual NPI has the same first and last
name and a taxonomy containing the indication's specialty. Everything else is
written to data/nppes/unresolved.csv for review. Stores practice city and state only.
    python3 scripts/ingest/nppes.py
"""
import re
import sys

import yaml

from common import DATA, ROOT, get, indications, write_csv

API = "https://npiregistry.cms.hhs.gov/api/"
FM = re.compile(r"^---\n(.*?)\n---\n", re.S)


def lookup(first, last):
    res = get(API, {"version": "2.1", "first_name": first, "last_name": last,
                    "enumeration_type": "NPI-1", "limit": 50}, pause=0.2)
    return res.get("results", [])


def main():
    specialties = {i.get("specialty", "").lower() for i in indications()} - {""}
    matched, unresolved = [], []
    for md in sorted((ROOT / "people").glob("*.md")):
        meta = yaml.safe_load(FM.match(md.read_text()).group(1))
        if meta.get("npi") or meta.get("identity"):  # skip resolved and initials-only names
            continue
        parts = re.sub(r"\b[A-Z]{1,3}\b\.?", "", meta["name"]).replace(".", " ").split()
        if len(parts) < 2:
            continue
        first, last = parts[0], parts[-1]
        hits = [r for r in lookup(first, last)
                if any(any(s in (t.get("desc") or "").lower() for s in specialties) for t in r.get("taxonomies", []))]
        row = {"person": md.stem, "name": meta["name"], "candidates": len(hits)}
        if len(hits) == 1:
            h = hits[0]
            loc = next((a for a in h.get("addresses", []) if a.get("address_purpose") == "LOCATION"), {})
            tax = next((t for t in h.get("taxonomies", []) if t.get("primary")), {})
            matched.append({**row, "npi": h["number"], "credential": h.get("basic", {}).get("credential", ""),
                            "taxonomy": tax.get("desc", ""), "city": loc.get("city", ""), "state": loc.get("state", "")})
        else:
            unresolved.append(row)
    write_csv(DATA / "nppes" / "matches.csv", matched,
              ["person", "name", "npi", "credential", "taxonomy", "city", "state", "candidates"])
    write_csv(DATA / "nppes" / "unresolved.csv", unresolved, ["person", "name", "candidates"])


if __name__ == "__main__":
    main()
