# PATENTS query3: analysis and reproducible solver

## The query

> "Which assignees, excluding UNIV CALIFORNIA itself, have cited patents assigned to
> UNIV CALIFORNIA, and what are the titles of the primary CPC subclasses associated
> with these citations?"

## Ground-truth semantics (reverse-engineered)

The ground truth follows the classic BigQuery `patents-public-data` citation join:

1. Cited side: publications whose `assignee_harmonized` contains the name
   `UNIV CALIFORNIA` (exact match — `UNIV CALIFORNIA AT SAN DIEGO` is excluded,
   which is why CALIFORNIA INST OF TECHN / G01V is not in the ground truth even
   though its patent US-2005165588-A1 cites US-6237292-B1).
2. Citing side: publications whose `citation[].publication_number` equals a cited
   publication number, with every name in the citing patent's `assignee_harmonized`
   reported (excluding `UNIV CALIFORNIA`).
3. CPC title: the citing patent's CPC entries with `first = true`, truncated to the
   4-character subclass and joined to `cpc_definition.titleFull`.

`solve_query3.py` implements exactly this over the released data. It finds three
citing publications:

| Citing publication | Rendered assignee | Cites | Primary CPC |
| --- | --- | --- | --- |
| US-10615444-B2 | BLOOM ENERGY CORP | US-6767662-B2 (UNIV CALIFORNIA) | H01M |
| US-9447521-B2 | CRYSTAL IS INC | US-2010025717-A1 (UNIV CALIFORNIA) | C30B |
| US-9437430-B2 | SCHOWALTER LEO J | US-2010025717-A1 (UNIV CALIFORNIA) | H01L |

All three resulting (assignee, titleFull) pairs are in the ground truth and the
derivation produces zero pairs outside it, confirming the join logic. However it
covers only **3 of the 28** ground-truth pairs.

## Why the remaining 25 pairs are unrecoverable from the released data

The released SQLite table keeps **one assignee per publication**: the
`Patents_info` natural-language summary renders a single name from what was
originally the multi-valued `assignee_harmonized` array, and no other column
carries assignee data. This loses information on both sides of the join:

- **Cited side.** The ground-truth citing patents cite UC patents whose released
  rows render a *different* co-assignee, so nothing identifies them as UC patents:
  - US-6245064-B1 is rendered as `ATRIONIX INC` (co-assigned to The Regents of the
    University of California). It is cited by US-8932208-B2 (the KENDALE AMAR /
    MAQUET CARDIOVASCULAR group, A61B) and by VIVANT MEDICAL INC's US-96199404-A
    filing (A61B).
  - US-2006293730-A1 is rendered as `RUBINSKY BORIS` (co-assigned to UC). It is
    cited by FARAPULSE INC's US-10709891-B2 (A61N).
  - The SANGAMO THERAPEUTICS, US HEALTH and BURRIGHT/KAEMMERER/VAN BILSEN groups
    fail the same way.
  The full text of US-6245064-B1 (title, abstract, description, claims) contains no
  mention of California or the Regents, so the link cannot be recovered from
  unstructured fields either.
- **Citing side.** Ground-truth rows such as `MAQUET CARDIOVASCULAR LLC` and
  `CRYSTAL IS INC | H01L` are co-assignees of citing patents whose released rows
  render only one name (`KENDALE AMAR`, `SCHOWALTER LEO J`). `MAQUET CARDIOVASCULAR
  LLC` appears nowhere in any `Patents_info` string. The individual co-assignees
  (e.g. SMART JOSEPH A, GRANDUSKY JAMES R, LIU SHIWEN) happen to coincide with
  `inventor_harmonized`, but that is a heuristic, not assignee data.

Since `validate.py` requires **every** ground-truth pair to appear in the answer,
no answer computed from the released databases can pass. This is corroborated by
the stored submissions: across `submissions/` and `leaderboard_submissions/`,
all 270 recorded runs of patents query3 fail validation (0% pass rate), including
the top leaderboard agents.

## Possible fixes

- Re-render `Patents_info` to include the full `assignee_harmonized` list, or add
  an `assignee_harmonized` column analogous to `inventor_harmonized`; or
- Regenerate `ground_truth.csv` from the released single-assignee data, which would
  reduce it to the three pairs derivable above (plus the individual co-assignees if
  inventors are meant to count as assignees).

## Reproducing

```bash
# from the repository root, with both PATENTS database files in place
python failure_analysis/patents_query3/solve_query3.py
```
