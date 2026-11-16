#!/usr/bin/env python3
"""Offline checks for the extractor and name matching. No network needed.

The sample text is written to look like the layouts we've seen on real pages
(agenda PDFs, news write-ups, FDA rosters). It is not copied from those pages.
    python3 scripts/crawl/selftest.py
"""
from extract import grounded, merge, rule_people, squash
from util import same_person

AGENDA = """
8:00 AM  New and Noteworthy in Psoriasis
Jane Q. Example, MD, MPH
9:15 AM  Hidradenitis Suppurativa Symposium (Non-CME)
Faculty: Robert Sample, MD, PhD; Maria de la Cruz, DO
Moderator: Dr. Ahmed Placeholder
"""
NEWS = """At the meeting, Linda Stein-Gold, MD, director of dermatology clinical research at Henry Ford Health, presented week 52 results. The study was led by investigators at several sites.
Session chair Kenji Tanaka, MD (University of Tokyo) opened the late-breaker session.
The New England Journal of Medicine published the data. University Hospital, MD is not a person.
"""
ROSTER = """Megan Example, M.D.
Professor of Dermatology, Mayo Clinic
Rochester, MN
Term: 08/31/2027
"""


def names(text):
    return {p["name"] for p in rule_people(text)}


def check(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg)
    return cond


def main():
    ok = True
    a = rule_people(AGENDA)
    ok &= check({"Jane Q. Example", "Robert Sample", "Maria de la Cruz", "Ahmed Placeholder"} <= {p["name"] for p in a},
                "agenda: finds all four people")
    ok &= check(any(p["name"] == "Ahmed Placeholder" and p["role"] == "chair" for p in a), "agenda: moderator → chair")
    n = rule_people(NEWS)
    got = {p["name"] for p in n}
    ok &= check({"Linda Stein-Gold", "Kenji Tanaka"} <= got, "news: finds presenter and chair")
    ok &= check(not any("University" in x or "Journal" in x or "England" in x for x in got), "news: no institutions as people")
    lsg = next(p for p in n if p["name"] == "Linda Stein-Gold")
    ok &= check("Henry Ford" in lsg["affiliation"] and lsg["role"] == "presenter", "news: affiliation and role for Stein-Gold")
    kt = next(p for p in n if p["name"] == "Kenji Tanaka")
    ok &= check("University of Tokyo" in kt["affiliation"] and kt["role"] == "chair", "news: affiliation in brackets, chair role")
    r = rule_people(ROSTER)
    ok &= check(any(p["name"] == "Megan Example" and "Mayo Clinic" in p["affiliation"] for p in r),
                "roster: affiliation on the next line")
    # names with titles or degrees glued on
    g = names("IPC Board Member Amy Example, MS, MD, chaired the session.\nKenneth G. Sample MD, MSc, said the change was shortsighted.")
    ok &= check("Amy Example" in g and "Kenneth G. Sample" in g, "names: titles in front and degree without comma removed")
    # plain author lists
    from extract import author_list_people
    a1 = {p["name"] for p in author_list_people("Menter A, Strober BE, Kaplan DH, Stein Gold L, et al.")}
    ok &= check({"A. Menter", "B. E. Strober", "D. H. Kaplan", "L. Stein Gold"} <= a1, "authors: PubMed short style")
    a2 = {p["name"] for p in author_list_people("Menter, Alan; Strober, Bruce E.; Kaplan, Daniel H.")}
    ok &= check({"Alan Menter", "Bruce E. Strober", "Daniel H. Kaplan"} <= a2, "authors: 'Last, First;' style")
    a3 = {p["name"] for p in author_list_people("Authors: Alan Menter, Bruce E. Strober, Daniel H. Kaplan and Joel M. Gelfand")}
    ok &= check({"Alan Menter", "Bruce E. Strober", "Daniel H. Kaplan", "Joel M. Gelfand"} <= a3, "authors: labelled 'First Last' list")
    a4 = author_list_people("Offices in New York, Los Angeles, San Diego and Boston")
    ok &= check(not a4, "authors: unlabelled city list ignored")
    from util import same_person as sp
    ok &= check(sp("B. E. Strober", "Bruce E. Strober") and sp("Dan Ollendorf", "Daniel A. Ollendorf")
                and sp("Linda F. Stein Gold", "Linda Stein Gold"), "match: initials, nicknames, middle initials")
    # matching
    ok &= check(same_person("Linda Stein-Gold", "Linda Stein Gold"), "match: hyphenated vs spaced surname")
    ok &= check(same_person("L. Stein Gold", "Linda Stein Gold"), "match: initial vs full first name")
    ok &= check(same_person("Julián Panés", "Julian Panes"), "match: accents")
    ok &= check(not same_person("L. Gold", "Linda Stein Gold"), "no match: 'Gold' alone vs 'Stein Gold'")
    ok &= check(not same_person("W. Wang", "Y. Wang"), "no match: different initials")
    ok &= check(not same_person("Wei Wang", "Wen Wang"), "no match: different first names")
    # grounding: an LLM answer whose quote isn't on the page is dropped
    page = squash(NEWS)
    ok &= check(grounded({"name": "Kenji Tanaka", "quote": "Session chair Kenji Tanaka, MD (University of Tokyo)"}, page),
                "grounding: real quote kept")
    ok &= check(not grounded({"name": "Kenji Tanaka", "quote": "Kenji Tanaka presented the phase 3 results"}, page),
                "grounding: invented quote dropped")
    ok &= check(not grounded({"name": "Mary Jones", "quote": "Session chair Kenji Tanaka, MD"}, page),
                "grounding: quote without the person's name dropped")
    # merge keeps one record per person, combining methods
    m = merge([{**lsg, "method": "rules"}, {**lsg, "name": "Linda Stein-Gold", "role": "named", "method": "llm"}])
    ok &= check(len(m) == 1 and m[0]["methods"] == ["rules", "llm"] and m[0]["role"] == "presenter", "merge: one record, both methods")
    print("\nALL PASSED" if ok else "\nSOME CHECKS FAILED")
    raise SystemExit(0 if ok else 1)


if __name__ == "__main__":
    main()
