# Schema

## Tree nodes

A node's ID is its path under `tree/` without the extension, for example `therapeutic-areas/immunology/mechanisms/il-23-pathway/guselkumab`. Its parent is the folder it sits in.

| Field | Required | Meaning |
|---|---|---|
| `title` | yes | Display name |
| `type` | yes | One of the node types below |
| `summary` | no | One or two sentences, shown in the parent's contents list |
| `order` | no | Sort position among siblings; otherwise alphabetical |
| `status` | no | `stub` for a placeholder that still needs work |
| `links` | no | Edges to other nodes: `- {rel: <link type>, to: <node id>}` |
| `sources` | no | `- {title: ..., url: ...}`; required for factual fields |
| any other key | no | A labeled fact, such as `brand`, `target`, `citation` or `doi` |

| Type | Used for |
|---|---|
| `root`, `category` | Grouping |
| `stakeholder` | A kind of expert |
| `disease` | A disease or indication |
| `mechanism` | A mechanism-of-action class |
| `asset` | A drug |
| `organization` | A company, society, center, payer or regulator |
| `evidence` | A guideline, trial publication or other citable work |
| `data-source` | A dataset |

| Link | From → to |
|---|---|
| `indicated_for` | drug → disease (approved) |
| `in_development_for` | drug → disease (in trials, not approved) |
| `markets` | company → drug |
| `covers` | evidence → disease, drug or mechanism |
| `issued_by` | guideline → society |
| `sponsored_by` | trial → company |
| `identifies` | data source → stakeholder type |
| `publishes` | organization → data source |
| `overlaps_with` | stakeholder → stakeholder |

You only write a link once. The other end shows it automatically.

## People

`people/<first-last>.md`. The file name must be lowercase with hyphens.

| Field | Required | Meaning |
|---|---|---|
| `name` | yes | Name as best confirmed |
| `type` | yes | `person` |
| `aliases` | no | Other spellings seen in sources |
| `identity` | no | Note when the name is unconfirmed, such as initials only |
| `status` | no | `auto` if added by the ingest scripts and not yet reviewed |
| `orcid`, `npi` | no | Identifiers. Used to merge records safely |
| `affiliations` | no | `- {text, as_of, source, org}`. `org` is an optional organization node ID |
| `evidence` | one of these | `- {node: <evidence node id>, role, author_position}` |
| `npi_record` | no | Added by `nppes.py`: credential, taxonomy, practice city and state, NPI Registry link, date checked |
| `payments` | no | Added by `openpayments.py`: year, total, number of companies, top companies with amounts and payment types |
| `status` | no | `auto` for people added by the data pulls and not yet reviewed. Delete the line once checked |
| `records` | one of these | `- {source, id, covers: <node id>, url, ...}` from the ingest scripts |

A person appears on every node their evidence or records cover, and on each of those nodes' ancestors.

## What not to store

Only professional information: names, affiliations, roles, identifiers, practice city and state. No home addresses, personal phone numbers or emails, and nothing about health or private life.
