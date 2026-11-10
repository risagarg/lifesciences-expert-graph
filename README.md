# Life Sciences Expert Graph

**A map of who the real experts are in healthcare and life sciences, and why.**

Diseases, drugs, companies and conferences are arranged as a tree. Every branch lists the named experts who belong there, and every expert has a reason they are listed: a guideline they wrote, a trial they led, or a talk they gave at a major conference.

Right now the deepest area is **inflammation and immunology**: psoriasis, atopic dermatitis, hidradenitis suppurativa, psoriatic arthritis, rheumatoid arthritis, Crohn's disease and ulcerative colitis.

---

## 1. Just want to look? Do nothing.

Click these, right here on GitHub:

- **[The tree](tree/README.md)**: start here and click down, like folders.
- **[All experts](EXPERTS.md)**: everyone, ranked by how many sources back them.

At the bottom of every page you'll see what's inside it, what it connects to, and its experts with the reason each one is there.

---

## 2. Want the visual, clickable tree? Run this once.

Open **Terminal** (on a Mac: press Cmd + Space, type `Terminal`, press Enter). Copy and paste this whole block, then press Enter:

```bash
git clone https://github.com/risagarg/lifesciences-expert-graph.git
cd lifesciences-expert-graph
pip3 install -r requirements.txt
python3 scripts/build.py --site
open site/index.html
```

It opens in your browser. That's it.

**Next time**, to get the latest version and open it again:

```bash
cd lifesciences-expert-graph
git pull
python3 scripts/build.py --site
open site/index.html
```

> **If something fails:** `git: command not found` means you need Git. Run `xcode-select --install` and try again. `pip3: command not found` means you need Python, which you can get from [python.org](https://www.python.org/downloads/). On Windows, use `start site/index.html` instead of `open site/index.html`.

### Using the visual tree

- **Click a branch** to open or close it.
- **Click any name** to see its details on the right.
- **Search** (top left) finds any disease, drug, company or person.
- **"Experts (N)"** inside a branch is the list of people for that branch. It's closed by default so it doesn't clutter the tree.
- The **detail panel** has two lists. *Contents* is the sub-branches (types of disease, drugs). *Experts* is the people.

---

## 3. How to read it

**Going down the tree** means "is a kind of" or "belongs under".
Immunology → Dermatology → Psoriasis → Plaque psoriasis.

**Dotted lines** connect things across branches:

| Line | Meaning | Example |
|---|---|---|
| indicated for | the drug is approved for that disease | Deucravacitinib → Plaque psoriasis |
| markets / develops | a company sells it, or is developing it | Takeda → Zasocitinib |
| covers | a guideline, trial or conference is about it | DDW 2025 → Ulcerative colitis |
| issued by / sponsored by | who ran the guideline, trial or conference | ACR Convergence 2025 → American College of Rheumatology |
| also expert in | the same person appears in other branches | |

**One person can show up in many places.** If someone has evidence in psoriasis and psoriatic arthritis, they appear under both.

---

## 4. Why someone is listed

Nobody is added without a source. Each person is listed because a source names them as one of these:

- **guideline author**: wrote an official treatment guideline (e.g. AAD–NPF psoriasis guidelines)
- **trial author**: author on a pivotal clinical trial paper
- **conference presenter or panelist**: gave a named talk at a major meeting
- **first author**: first author on a conference abstract, where the source doesn't say who presented

Conferences so far: **AAD 2025 and 2026**, **EADV 2025**, **Fall Clinical Dermatology 2025**, **ACR Convergence 2025** and **DDW 2025**.

Each expert shows:

- **Sources**: how many independent sources name them. More sources means stronger evidence.
- **Last seen**: the most recent year a source names them. This suggests they're active, but **it does not confirm they're alive or reachable**. Check before contacting anyone.
- **Flags**: *name unconfirmed* means only initials were in the source. *industry* means a company employee.

---

## 5. Adding to it

You need the repo on your computer (step 2 above). Then:

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

**Pulling experts in bulk** from trial registries, PubMed and Medicare data: see [ingest/README.md](ingest/README.md).

---

## What's in the repo

```
tree/                  the tree itself
  therapeutic-areas/   diseases (immunology is built out)
  mechanisms/          drugs, grouped by how they work
  organizations/       companies, societies, regulators
  evidence/            guidelines, trials, conferences: the reasons people are listed
  stakeholders/        kinds of experts (clinicians, investigators, payers...)
  data-sources/        public datasets for bulk pulls
people/                one file per expert
EXPERTS.md             every expert, ranked
scripts/build.py       rebuilds links, expert lists and the visual site
```
