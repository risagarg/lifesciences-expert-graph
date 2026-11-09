# Sentari Expertise Tree

A map of healthcare and life sciences stakeholders and expertise, kept as plain files. The folder tree is the taxonomy, and `links:` inside each file connect nodes across branches into a graph.

## Layout

```
tree/
  stakeholders/        who holds expertise (clinicians, investigators, payers…)
  therapeutic-areas/   disease taxonomy, seeded with psoriasis
  mechanisms/          drugs grouped by mechanism of action
  data-sources/        public datasets that identify people and supply evidence
scripts/
  build_site.py        validates the tree and builds the clickable site
  site_template.html   the site's page; the build injects the tree data
SCHEMA.md              node types, fields and link types
```

Browse on GitHub by clicking through `tree/`. Each folder's `README.md` describes that node, and each single `.md` file is a leaf.

## Add a node

1. Make a folder with a `README.md` if the node will have children, or a single `.md` file if it is a leaf. Use lowercase-hyphen names.
2. Add frontmatter with at least `title` and `type`. See `SCHEMA.md`.
3. Cite a source for every factual field.
4. Run the build to check it.

## Build the site

```
pip install -r requirements.txt
python3 scripts/build_site.py
open site/index.html
```

The build fails on a missing title or type, a bad folder name, or a link to a node that doesn't exist. `site/` is generated and not committed.
