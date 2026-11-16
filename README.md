# Life Sciences Expert Graph

The Diseases, drugs, companies and conferences are arranged as a tree. Every branch lists the named experts, and every expert has a reason they are listed: a guideline they wrote, a trial they led, or a talk they gave at a major conference.

As of right now, the area the most built out is **inflammation and immunology**: psoriasis, atopic dermatitis, hidradenitis suppurativa, psoriatic arthritis, rheumatoid arthritis, Crohn's disease and ulcerative colitis. **Obesity** (GLP-1 and related drugs) has been started.


- **[The tree](tree/README.md)**: start here and click down, like folders.
- **[All experts](EXPERTS.md)**: all experts, ranked by how many sources back them.

At the bottom of every page you'll see what's inside it, what it connects to, and its experts with the reason each one is there.

---

## 2. Visual Tree

In terminal - 

```bash
git clone https://github.com/risagarg/lifesciences-expert-graph.git
cd lifesciences-expert-graph
pip3 install -r requirements.txt
python3 scripts/build.py --site
open site/index.html
```
to get the latest version and open it again:

```bash
cd lifesciences-expert-graph
git pull
python3 scripts/build.py --site
open site/index.html
```

### Using the visual tree

- **Click a branch** to open or close it.
- **Click any name** to see its details on the right.
- **Search** (top left) finds any disease, drug, company or person.
- **"Experts (N)"** inside a branch is the list of people for that branch. It's closed by default so it doesn't clutter the tree.
- The **detail panel** has two lists. *Contents* is the sub-branches (types of disease, drugs). *Experts* is the people.

---

**Going down the tree** means "is a kind of" or "belongs under".
Immunology → Dermatology → Psoriasis → Plaque psoriasis.

**Dotted lines** connect things across branches:

| Line | Meaning | Example |
|---|---|---|
| indicated for | the drug is approved for that disease | Deucravacitinib → Plaque psoriasis |
| in development for | the drug is in trials for that disease, not yet approved | Retatrutide → Obesity |
| markets / develops | a company sells it, or is developing it | Takeda → Zasocitinib |
| covers | a guideline, trial or conference is about it | DDW 2025 → Ulcerative colitis |
| issued by / sponsored by | who ran the guideline, trial or conference | ACR Convergence 2025 → American College of Rheumatology |
| also expert in | the same person appears in other branches | |


Each person is listed because a source names them as one of these:

- **guideline author**: wrote an official treatment guideline (e.g. AAD–NPF psoriasis guidelines)
- **trial author**: author on a pivotal clinical trial paper
- **conference presenter or panelist**: gave a named talk at a major meeting
- **first author**: first author on a conference abstract, where the source doesn't say who presented
- **advisory committee member**: sits (or sat) on an FDA advisory committee
- **value assessment author or reviewer**: wrote or reviewed an ICER drug value report (payer perspective)
- **organization leader**: leads a patient organization
- **data pull** (*auto, not reviewed*): found automatically in trial registries, PubMed or Medicare prescribing data

Conferences so far:

- **Skin:** AAD 2025 and 2026, EADV 2025, Fall Clinical 2025, Winter Clinical Hawaii 2026, Maui Derm 2026
- **Joints:** ACR Convergence 2025, EULAR 2026
- **Gut:** DDW 2025, ECCO 2026
- **Obesity and diabetes:** ObesityWeek 2025, ADA Scientific Sessions 2026

Talks marked *non-CME* are company-sponsored product talks, so the speaker is likely paid by that company.

Each expert shows:

- **Sources**: how many independent sources name them
- **Last seen**: the most recent year a source names them. This suggests they're active.


1. **Add or edit a file.**
   - A **folder with a `README.md`** is a branch.
   - A **single `.md` file** is an end point.
   - Copy a file next to it and change the details. [SCHEMA.md](SCHEMA.md) lists every field.
2. **Add an expert:** make a file in `people/` and point it at a guideline, trial or conference in `tree/evidence/`. Copy `people/frank-behrens.md` as a short example.
3. **Add a conference:** make a file in `tree/evidence/conferences/`. Copy `ddw-2025.md`.
4. **Rebuild and upload:**

```bash
python3 scripts/build.py
git add -A
git commit -m "Say what you added"
git push
```

**Only edit above the `GENERATED` line** in any file. Everything below it is rewritten automatically by `build.py`.

**Pulling experts in bulk:** a GitHub Action runs every Monday. It pulls people from ClinicalTrials.gov, PubMed and Medicare prescribing data, looks up their NPI, and adds their industry payments from Open Payments. To add a disease to it, or to run it now, see [ingest/README.md](ingest/README.md).

**Crawler (test version):** reads conference pages, FDA rosters and news write-ups and finds the people on them, scored against the experts we entered by hand. See [crawl/README.md](crawl/README.md).

---

```
tree/                      the tree itself
  therapeutic-areas/       diseases, by area
    immunology/            skin, joint and gut inflammation (built out)
      mechanisms/          the drugs, grouped by pathway (TNF, IL-17, IL-23...)
    cardiometabolic/       obesity and type 2 diabetes (started)
      mechanisms/          GLP-1 and related drugs
  organizations/           companies, societies, regulators
  evidence/                guidelines, trials, conferences, FDA committees, ICER reports: the reasons people are listed
  stakeholders/            kinds of experts (clinicians, investigators, payers...)
  data-sources/            public datasets for bulk pulls
people/                    one file per expert
ingest/                    which diseases the weekly data pull covers
crawl/                     the crawler's sources, report and results
EXPERTS.md                 every expert, ranked
scripts/build.py           rebuilds links, expert lists and the visual site
```
