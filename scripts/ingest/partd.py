#!/usr/bin/env python3
"""Rank prescribers of each indication's drugs using Medicare Part D by Provider and Drug.

Finds the newest year in the data.cms.gov catalog, pulls rows for each generic
name in indications.yml, and sums claims per prescriber NPI.
Writes data/partd/<slug>.csv.
    python3 scripts/ingest/partd.py [slug ...]
CMS suppresses small counts, so low-volume prescribers are missing. See the CMS methodology for the threshold.
"""
import collections
import re
import sys

from common import DATA, get, indications, write_csv

CATALOG = "https://data.cms.gov/data.json"
TITLE = "Medicare Part D Prescribers - by Provider and Drug"
FIELDS = ["npi", "last_name", "first_name", "credential", "specialty", "city", "state",
          "total_claims", "total_beneficiaries", "drugs", "data_year"]


def latest_dataset():
    cat = get(CATALOG)
    ds = next(d for d in cat["dataset"] if d.get("title") == TITLE)
    best = None
    for dist in ds.get("distribution", []):
        url = dist.get("accessURL") or dist.get("downloadURL") or ""
        m = re.search(r"(\d{4})-12-31", dist.get("title", ""))
        if "/data-api/v1/dataset/" in url and m and (best is None or m.group(1) > best[0]):
            best = (m.group(1), url.split("/data-viewer")[0].rstrip("/"))
    if not best:
        raise RuntimeError("No API distribution found for " + TITLE)
    year, url = best
    return year, url if url.endswith("/data") else url + "/data"


def rows_for(url, generic):
    offset = 0
    while True:
        page = get(url, {"keyword": generic, "size": 5000, "offset": offset})
        if not page:
            return
        for r in page:
            if (r.get("Gnrc_Name") or "").lower().startswith(generic.lower()):
                yield r
        offset += len(page)


def main(only):
    year, url = latest_dataset()
    print(f"Part D data year {year}: {url}", file=sys.stderr)
    for ind in indications(only):
        agg = {}
        for g in ind.get("partd_generics", []):
            for r in rows_for(url, g):
                npi = r["Prscrbr_NPI"]
                a = agg.setdefault(npi, {"npi": npi, "last_name": r.get("Prscrbr_Last_Org_Name"),
                                         "first_name": r.get("Prscrbr_First_Name"), "credential": r.get("Prscrbr_Crdntls", ""),
                                         "specialty": r.get("Prscrbr_Type"), "city": r.get("Prscrbr_City"),
                                         "state": r.get("Prscrbr_State_Abrvtn"), "total_claims": 0,
                                         "total_beneficiaries": 0, "_drugs": collections.Counter(), "data_year": year})
                claims = int(float(r.get("Tot_Clms") or 0))
                a["total_claims"] += claims
                a["total_beneficiaries"] += int(float(r.get("Tot_Benes") or 0))
                a["_drugs"][r.get("Gnrc_Name")] += claims
        rows = sorted(agg.values(), key=lambda a: -a["total_claims"])
        for a in rows:
            a["drugs"] = "; ".join(f"{d} ({c})" for d, c in a.pop("_drugs").most_common())
        write_csv(DATA / "partd" / f"{ind['slug']}.csv", rows, FIELDS)


if __name__ == "__main__":
    main(sys.argv[1:])
