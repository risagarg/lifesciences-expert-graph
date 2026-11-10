# Lifesciences Expert Graph

A growing map of healthcare and life sciences expertise: diseases, drugs, organizations, evidence, and the named people who know each area. Everything is plain files you can browse and edit right here on GitHub.

**Start browsing:** [the tree](tree/README.md) · [all experts](EXPERTS.md)

## How it's organized

```
tree/                  the taxonomy: one folder or file per node
  stakeholders/        kinds of experts (clinicians, investigators, payers…)
  therapeutic-areas/   diseases: immunology built out, other areas started
  mechanisms/          drugs grouped by mechanism
  organizations/       companies, societies, academic centers, payers, regulators
  evidence/            guidelines and trials that show who knows what
  data-sources/        public datasets the ingest scripts pull from
people/                one file per named expert
EXPERTS.md             every expert, ranked
ingest/                which indications to pull experts for, and how
scripts/               build and ingest scripts
```

Every page ends with a generated section that links to its parent, children, connections and experts, so you can click through the whole graph on GitHub.

## How someone becomes an expert here

A person is linked to **evidence** (a guideline they wrote, a trial they ran or published, papers, prescribing data). Each piece of evidence says what it **covers** (a disease, a drug, a mechanism). Those links decide which pages a person appears on and how they rank. Nobody is added without a cited source.

## Adding to it

- **A node:** add a folder with a `README.md` (if it will have children) or a single `.md` file. Fill in the frontmatter (see [SCHEMA.md](SCHEMA.md)). Cite a source for every fact.
- **A person by hand:** add `people/<first-last>.md` with `name` and at least one `evidence` entry pointing to an evidence node.
- **Experts at scale:** add an indication to [ingest/indications.yml](ingest/indications.yml) and run the ingest scripts (see [ingest/README.md](ingest/README.md)).
- **Then rebuild the links:**

```
pip install -r requirements.txt
python3 scripts/build.py
```

The build fails on broken links, unknown nodes or bad file names. Edit only above the `GENERATED` line in each file. Everything below it is rewritten.

`python3 scripts/build.py --site` also writes `site/index.html`, a visual version of the tree you can open locally. It isn't committed.
