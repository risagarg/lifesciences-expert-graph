#!/usr/bin/env python3
"""Summarize industry payments to each person with an NPI, from CMS Open Payments.

Uses the newest "General Payment Data" year in the Open Payments catalog and
queries it by covered_recipient_npi. Writes a short summary to each person's
file as `payments` (year, total, top companies with amount and payment types)
and the full breakdown to data/openpayments/by_person.csv.
Research payments are a separate dataset and are not included.
    python3 scripts/ingest/openpayments.py
"""
import collections
import re
import sys

from common import DATA, ROOT, get, read_person, write_csv, write_person

BASE = "https://openpaymentsdata.cms.gov/api/1/"


def latest_general():
    items = get(BASE + "metastore/schemas/dataset/items")
    best = None
    for d in items:
        title = d.get("title", "")
        m = re.match(r"^(\d{4}) General Payment Data$", title.strip())
        if m and (best is None or m.group(1) > best[0]):
            best = (m.group(1), d["identifier"])
    if not best:
        raise RuntimeError("No 'YYYY General Payment Data' dataset found in the Open Payments catalog")
    return best


def col(row, *needles):
    """Find a column by fragments, since CMS renames columns between years."""
    for k in row:
        if all(n in k.lower() for n in needles):
            return k
    return None


def payments_for(dataset, npi):
    out, offset = [], 0
    while True:
        page = get(f"{BASE}datastore/query/{dataset}/0", {
            "conditions[0][property]": "covered_recipient_npi", "conditions[0][value]": npi,
            "conditions[0][operator]": "=", "limit": 500, "offset": offset}, pause=0.2)
        rows = page.get("results", [])
        out += rows
        if len(rows) < 500:
            return out
        offset += 500


def main():
    year, dataset = latest_general()
    print(f"Open Payments general payments, program year {year}: {dataset}", file=sys.stderr)
    rows = []
    for md in sorted((ROOT / "people").glob("*.md")):
        meta, rest = read_person(md)
        npi = str(meta.get("npi") or "")
        if not npi:
            continue
        pays = payments_for(dataset, npi)
        by_co = collections.defaultdict(lambda: {"usd": 0.0, "kinds": collections.Counter()})
        if pays:
            amt, co, kind = (col(pays[0], "total_amount_of_payment"), col(pays[0], "making_payment_name"),
                             col(pays[0], "nature_of_payment"))
            for p in pays:
                usd = float(p.get(amt) or 0)
                c = by_co[(p.get(co) or "Unknown").strip()]
                c["usd"] += usd
                c["kinds"][(p.get(kind) or "Other").strip()] += usd
        total = round(sum(c["usd"] for c in by_co.values()), 2)
        top = sorted(by_co.items(), key=lambda kv: -kv[1]["usd"])
        meta["payments"] = {
            "source": "CMS Open Payments, general payments", "year": int(year), "total_usd": total,
            "companies": len(by_co),
            "top": [{"company": k, "usd": round(v["usd"], 2),
                     "types": [t for t, _ in v["kinds"].most_common(3)]} for k, v in top[:5]],
            "url": "https://openpaymentsdata.cms.gov/",
        }
        write_person(md, meta, rest)
        for k, v in top:
            rows.append({"person": md.stem, "npi": npi, "year": year, "company": k, "usd": round(v["usd"], 2),
                         "types": "; ".join(f"{t} ({round(u, 2)})" for t, u in v["kinds"].most_common())})
        if not top:
            rows.append({"person": md.stem, "npi": npi, "year": year, "company": "", "usd": 0, "types": ""})
    write_csv(DATA / "openpayments" / "by_person.csv", rows, ["person", "npi", "year", "company", "usd", "types"])


if __name__ == "__main__":
    main()
