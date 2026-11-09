#!/usr/bin/env python3
"""Rank publishing authors for each indication using PubMed E-utilities.

Writes data/pubmed/<slug>.csv with one row per author, grouped by ORCID when
PubMed has one and otherwise by surname + forename.
    python3 scripts/ingest/pubmed.py [slug ...]
Set NCBI_API_KEY to raise the rate limit from 3 to 10 requests per second.
"""
import collections
import os
import sys
import xml.etree.ElementTree as ET

from common import DATA, get, indications, write_csv

EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"
KEY = {"api_key": os.environ["NCBI_API_KEY"]} if os.environ.get("NCBI_API_KEY") else {}
PAUSE = 0.12 if KEY else 0.4
MAX_PAPERS = 5000
FIELDS = ["author_key", "name", "last_name", "fore_name", "orcid", "papers", "first_or_last",
          "latest_year", "latest_affiliation", "pmids"]


def main(only):
    for ind in indications(only):
        res = get(EUTILS + "esearch.fcgi", {"db": "pubmed", "term": ind["pubmed_query"], "retmax": 0,
                                            "usehistory": "y", "retmode": "json", **KEY}, pause=PAUSE)["esearchresult"]
        total = min(int(res["count"]), MAX_PAPERS)
        print(f"{ind['slug']}: {res['count']} papers, reading {total}", file=sys.stderr)
        authors = {}
        for start in range(0, total, 200):
            xml = get(EUTILS + "efetch.fcgi", {"db": "pubmed", "query_key": res["querykey"], "WebEnv": res["webenv"],
                                               "retstart": start, "retmax": 200, "retmode": "xml", **KEY},
                      as_json=False, pause=PAUSE)
            for art in ET.fromstring(xml).iter("PubmedArticle"):
                pmid = art.findtext(".//PMID")
                year = art.findtext(".//JournalIssue/PubDate/Year") or ""
                alist = art.findall(".//AuthorList/Author")
                for i, a in enumerate(alist):
                    last, fore = a.findtext("LastName"), a.findtext("ForeName") or a.findtext("Initials") or ""
                    if not last:
                        continue
                    orcid = next((x.text.strip().split("/")[-1] for x in a.findall("Identifier")
                                  if x.get("Source") == "ORCID" and x.text), "")
                    key = f"orcid:{orcid}" if orcid else f"name:{last.lower()}|{fore.lower()}"
                    r = authors.setdefault(key, {"author_key": key, "last_name": last, "fore_name": fore,
                                                 "name": f"{fore} {last}".strip(), "orcid": orcid, "papers": 0,
                                                 "first_or_last": 0, "latest_year": "", "latest_affiliation": "",
                                                 "_pmids": []})
                    r["papers"] += 1
                    r["first_or_last"] += int(i == 0 or i == len(alist) - 1)
                    r["_pmids"].append(pmid)
                    aff = a.findtext(".//AffiliationInfo/Affiliation")
                    if aff and year >= r["latest_year"]:
                        r["latest_year"], r["latest_affiliation"] = year, aff
        rows = sorted(authors.values(), key=lambda r: (-r["papers"], -r["first_or_last"]))
        for r in rows:
            r["pmids"] = " ".join(r.pop("_pmids")[:20])
        write_csv(DATA / "pubmed" / f"{ind['slug']}.csv", rows, FIELDS)


if __name__ == "__main__":
    main(sys.argv[1:])
