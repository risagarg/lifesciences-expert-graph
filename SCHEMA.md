# Schema

A node's ID is its path under `tree/` without the extension, for example `mechanisms/il-23-pathway/guselkumab`. A node's parent is its containing folder.

## Fields

| Field | Required | Meaning |
|---|---|---|
| `title` | yes | Display name |
| `type` | yes | One of the node types below |
| `summary` | no | One or two sentences shown at the top of the node |
| `order` | no | Sort position among siblings; otherwise alphabetical |
| `status` | no | `stub` for a placeholder that still needs work |
| `links` | no | Cross-branch edges: `- {rel: <link type>, to: <node id>}` |
| `sources` | no | `- {title: ..., url: ...}`; required for factual fields |
| any other key | no | Shown as a labeled field, such as `brand`, `target` or `route` |

Markdown below the frontmatter is shown as the node body.

## Node types

| Type | Used for |
|---|---|
| `root` | The top of the tree |
| `category` | Grouping nodes |
| `stakeholder` | A kind of person or organization with expertise |
| `disease` | A disease or indication |
| `mechanism` | A mechanism-of-action class |
| `asset` | A drug |
| `data-source` | A dataset that supplies nodes or evidence |

## Link types

| Rel | From → to |
|---|---|
| `indicated_for` | asset → disease |
| `identifies` | data-source → stakeholder |
| `overlaps_with` | stakeholder → stakeholder |

The site shows each link on both ends, so backlinks don't need to be written by hand.

## Next

Individual people won't live in these files. They belong in a database keyed to tree node IDs, with each edge carrying its source, date and match confidence.
