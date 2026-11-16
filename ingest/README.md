# Ingest: pulling experts from public data

These scripts fill the graph automatically. For every disease in [`indications.yml`](indications.yml), they find named people in public data and add the top ones to `people/`, each with the record that put them there.

**You don't have to run anything.** A GitHub Action ([`.github/workflows/ingest.yml`](../.github/workflows/ingest.yml)) runs it all on GitHub's servers every Monday, and whenever `indications.yml` or these scripts change. It commits the results back to the repo. To run it now: go to the repo's **Actions** tab, click **ingest**, then **Run workflow**.

## What each step does

| Step | Source | Who it finds | Output |
|---|---|---|---|
| 1 | ClinicalTrials.gov | Named trial officials (principal investigators, study chairs) | `data/clinicaltrials/<disease>.csv` |
| 2 | PubMed | Most-published authors on the disease (newest 5,000 papers since 2021) | `data/pubmed/<disease>.csv` |
| 3 | Medicare Part D | Top prescribers of the disease's drugs, counting only the matching specialty | `data/partd/<disease>.csv` |
| 4 | — | Adds the top 20 from each source to `people/` | `people/*.md` |
| 5 | NPI Registry | Each person's NPI, specialty and practice city/state, if exactly one matches | `data/nppes/matches.csv`, `unresolved.csv` |
| 6 | CMS Open Payments | Industry payments to each person with an NPI (newest year, by company) | `data/openpayments/by_person.csv` |

The NPI and payments show on each person's page under **Practice and industry ties**. Anyone with payments is flagged *industry-paid* in [EXPERTS.md](../EXPERTS.md).

The full PubMed and ClinicalTrials.gov tables are large, so they aren't committed. Each run attaches them as a download (Actions > the run > **ingest-data**). The people chosen from them are committed in `people/`.

## Add a disease

Add an entry to `indications.yml` and push. Each entry points at a tree node and gives:

- `clinicaltrials_condition`: the ClinicalTrials.gov condition search
- `pubmed_query`: the PubMed search
- `specialty`: the CMS/NPI specialty (e.g. Dermatology). Part D prescribers and NPI matches must have it
- `partd_generics`: drugs whose prescribers count as evidence for this disease

Copy an entry next to it. The comments in the file explain when to leave `partd_generics` out.

## Rules

- People added this way are marked **auto, not reviewed** until someone checks them and deletes the `status: auto` line.
- A new name merges into an existing person only on the same ORCID, the same NPI, or the same full first and last name. Initials alone never merge.
- Placeholder officials ("Medical Director", "Clinical Trials, [Company]") and company study directors on company-run trials are skipped.
- Only professional information is kept: name, affiliation, NPI, specialty, practice city and state, and public payment totals. No street addresses.

## Run it on your own computer (optional)

From the repo folder:

```bash
pip3 install -r requirements.txt
python3 scripts/ingest/clinicaltrials.py
python3 scripts/ingest/pubmed.py
python3 scripts/ingest/partd.py
python3 scripts/ingest/promote.py --top 20
python3 scripts/ingest/nppes.py
python3 scripts/ingest/openpayments.py
python3 scripts/build.py
```

Add a disease's slug to any step to run just that one, e.g. `python3 scripts/ingest/pubmed.py atopic-dermatitis`.

## Status

The scripts have been tested end to end against simulated API responses, but not yet against the live sites (they're blocked from the environment that wrote them). Check the first Action run's output before relying on it.
