#!/usr/bin/env python3
"""Look up NPIs for people in people/ who don't have one yet, via the NPI Registry API.

Only accepts a match when exactly one individual NPI has the same first and last
name and a taxonomy containing one of the specialties in ingest/indications.yml.
Matches are written back to the person's file as `npi` and `npi_record`
(credential, primary taxonomy, practice city and state, no street address).
Everything else goes to data/nppes/unresolved.csv for review.
    python3 scripts/ingest/nppes.py
"""
import datetime
import re

from common import DATA, ROOT, get, indications, read_person, write_csv, write_person

API = "https://npiregistry.cms.hhs.gov/api/"


def lookup(first, last):
    res = get(API, {"version": "2.1", "first_name": first, "last_name": last,
                    "enumeration_type": "NPI-1", "limit": 50}, pause=0.2)
    return res.get("results", [])


def main():
    specialties = {i.get("specialty", "").lower() for i in indications()} - {""}
    today = datetime.date.today().isoformat()
    matched, unresolved = [], []
    for md in sorted((ROOT / "people").glob("*.md")):
        meta, rest = read_person(md)
        if meta.get("npi") or meta.get("identity"):  # skip resolved and initials-only names
            continue
        name = re.sub(r"\(.*?\)", "", meta["name"])
        parts = re.sub(r"\b[A-Z]\.?(?=\s|$)", "", name).replace(".", " ").split()
        if len(parts) < 2:
            continue
        first, last = parts[0], parts[-1]
        hits = [r for r in lookup(first, last)
                if any(any(s in (t.get("desc") or "").lower() for s in specialties) for t in r.get("taxonomies", []))]
        row = {"person": md.stem, "name": meta["name"], "candidates": len(hits)}
        if len(hits) != 1:
            unresolved.append(row)
            continue
        h = hits[0]
        loc = next((a for a in h.get("addresses", []) if a.get("address_purpose") == "LOCATION"), {})
        tax = next((t for t in h.get("taxonomies", []) if t.get("primary")), {})
        rec = {"credential": h.get("basic", {}).get("credential", ""), "taxonomy": tax.get("desc", ""),
               "practice": f"{loc.get('city', '').title()}, {loc.get('state', '')}".strip(", "),
               "checked": today, "url": f"https://npiregistry.cms.hhs.gov/provider-view/{h['number']}"}
        meta["npi"] = str(h["number"])
        meta["npi_record"] = rec
        write_person(md, meta, rest)
        matched.append({**row, "npi": h["number"], **rec})
    write_csv(DATA / "nppes" / "matches.csv", matched,
              ["person", "name", "npi", "credential", "taxonomy", "practice", "checked", "candidates"])
    write_csv(DATA / "nppes" / "unresolved.csv", unresolved, ["person", "name", "candidates"])


if __name__ == "__main__":
    main()
