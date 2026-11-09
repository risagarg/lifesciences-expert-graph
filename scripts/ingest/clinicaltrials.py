#!/usr/bin/env python3
"""Pull named study officials for each indication from ClinicalTrials.gov API v2.

Writes data/clinicaltrials/<slug>.csv with one row per (trial, official).
    python3 scripts/ingest/clinicaltrials.py [slug ...]
"""
import sys

from common import DATA, get, indications, write_csv

API = "https://clinicaltrials.gov/api/v2/studies"
FIELDS = ["nct_id", "title", "phase", "status", "sponsor", "sponsor_class", "start_date",
          "official_name", "official_affiliation", "official_role"]


def studies(condition):
    token = None
    while True:
        params = {"query.cond": condition, "pageSize": 1000, "format": "json"}
        if token:
            params["pageToken"] = token
        page = get(API, params)
        yield from page.get("studies", [])
        token = page.get("nextPageToken")
        if not token:
            return


def main(only):
    for ind in indications(only):
        rows = []
        for s in studies(ind["clinicaltrials_condition"]):
            p = s.get("protocolSection", {})
            ident, status = p.get("identificationModule", {}), p.get("statusModule", {})
            sponsor = p.get("sponsorCollaboratorsModule", {}).get("leadSponsor", {})
            base = {"nct_id": ident.get("nctId"), "title": ident.get("briefTitle"),
                    "phase": "|".join(p.get("designModule", {}).get("phases", []) or []),
                    "status": status.get("overallStatus"),
                    "start_date": (status.get("startDateStruct") or {}).get("date"),
                    "sponsor": sponsor.get("name"), "sponsor_class": sponsor.get("class")}
            for o in p.get("contactsLocationsModule", {}).get("overallOfficials", []) or []:
                if o.get("name"):
                    rows.append({**base, "official_name": o.get("name"),
                                 "official_affiliation": o.get("affiliation"), "official_role": o.get("role")})
        write_csv(DATA / "clinicaltrials" / f"{ind['slug']}.csv", rows, FIELDS)


if __name__ == "__main__":
    main(sys.argv[1:])
