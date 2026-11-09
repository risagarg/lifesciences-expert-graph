# Ingest

Scripts that pull named experts from public data for each indication in `indications.yml`.

| Step | Script | Output |
|---|---|---|
| Trial officials | `scripts/ingest/clinicaltrials.py` | `data/clinicaltrials/<slug>.csv` |
| Publishing authors | `scripts/ingest/pubmed.py` | `data/pubmed/<slug>.csv` |
| Top prescribers | `scripts/ingest/partd.py` | `data/partd/<slug>.csv` |
| Add top candidates to `people/` | `scripts/ingest/promote.py --top 25` | new or updated `people/*.md` |
| NPI lookups for people without one | `scripts/ingest/nppes.py` | `data/nppes/matches.csv`, `unresolved.csv` |

Then run `python3 scripts/build.py` to refresh the indexes.

## Run it

On your own computer, from the repo folder:

```
pip install -r requirements.txt
python3 scripts/ingest/clinicaltrials.py
python3 scripts/ingest/pubmed.py
python3 scripts/ingest/partd.py
python3 scripts/ingest/promote.py --top 25
python3 scripts/ingest/nppes.py
python3 scripts/build.py
```

Or let GitHub run it weekly: copy `ops/ingest-workflow.yml` to `.github/workflows/ingest.yml`. It also runs whenever `indications.yml` changes.

## Add an indication

Add an entry to `indications.yml` that points at a tree node, with a ClinicalTrials.gov condition, a PubMed query, the NPI specialty text and the generic drug names to rank prescribers by.

## Rules

- People added this way get `status: auto` until someone reviews them.
- A candidate merges into an existing person only on the same ORCID, the same NPI, or the same full first and last name. Initials alone never merge.
- Only professional information is kept: name, affiliation, NPI, practice city and state.
- Open Payments is not pulled yet. Its datasets are large and need their own query script.

## Status

These scripts haven't been run against the live APIs yet. The session that wrote them couldn't reach those sites. Check the first run's output before relying on it.
