# PATENTS ground-truth audit (queries 1-3)

All three PATENTS queries had a 0% pass rate across the 270 recorded runs in
`submissions/` and `leaderboard_submissions/`. This audit reproduces each
ground truth from the released data. Outcome:

| Query | Ground truth derivable from released data? | Action |
| --- | --- | --- |
| query1 | Yes — exact match (50/50 codes) | none |
| query2 | Yes — exact match (23/23 rows) | none |
| query3 | No — only 3 of 28 pairs derivable | ground truth regenerated |

## query1 and query2: correct, just hard

`reproduce_query1_query2.py` reproduces both ground truths exactly with this
recipe:

- count one filing per CPC entry flagged `first = true` (duplicate entries in
  the released JSON are counted as released);
- filing year taken from the natural-language `filing_date`;
- EMA computed over only the years present for each group (gap years are not
  zero-filled), seeded at zero, i.e. `ema = alpha * count` for the first year;
- best year = argmax of the EMA series;
- query1: subclass level (4-character symbol, level 5), alpha 0.2, keep groups
  with best year 2022;
- query2: country DE (publication-number prefix), grant date in H2 2019, class
  level (3-character symbol, level 4), alpha 0.1.

The 0% pass rate on these two queries reflects difficulty (agents must guess
the exact EMA conventions), not data problems.

## query3: ground truth not derivable from released data — regenerated

The query: "Which assignees, excluding UNIV CALIFORNIA itself, have cited
patents assigned to UNIV CALIFORNIA, and what are the titles of the primary CPC
subclasses associated with these citations?"

### Ground-truth semantics (reverse-engineered)

The original ground truth follows the classic BigQuery `patents-public-data`
citation join:

1. Cited side: publications whose `assignee_harmonized` contains the name
   `UNIV CALIFORNIA` (exact match — `UNIV CALIFORNIA AT SAN DIEGO` is excluded,
   which is why CALIFORNIA INST OF TECHN / G01V was not in the ground truth even
   though its patent US-2005165588-A1 cites US-6237292-B1).
2. Citing side: publications whose `citation[].publication_number` equals a
   cited publication number, with every name in the citing patent's
   `assignee_harmonized` reported (excluding `UNIV CALIFORNIA`).
3. CPC title: the citing patent's CPC entries with `first = true`, truncated to
   the 4-character subclass and joined to `cpc_definition.titleFull`.

`solve_query3.py` implements exactly this over the released data and finds
three citing publications:

| Citing publication | Rendered assignee | Cites | Primary CPC |
| --- | --- | --- | --- |
| US-10615444-B2 | BLOOM ENERGY CORP | US-6767662-B2 (UNIV CALIFORNIA) | H01M |
| US-9447521-B2 | CRYSTAL IS INC | US-2010025717-A1 (UNIV CALIFORNIA) | C30B |
| US-9437430-B2 | SCHOWALTER LEO J | US-2010025717-A1 (UNIV CALIFORNIA) | H01L |

All three resulting (assignee, titleFull) pairs were in the original ground
truth and the derivation produces zero pairs outside it, confirming the join
logic. However it covered only 3 of the original 28 pairs.

### Why the other 25 pairs were unrecoverable

The released SQLite table keeps one assignee per publication: the
`Patents_info` natural-language summary renders a single name from what was
originally the multi-valued `assignee_harmonized` array, and no other column
carries assignee data. This loses information on both sides of the join:

- Cited side. The original ground-truth citing patents cite UC patents whose
  released rows render a different co-assignee, so nothing identifies them as
  UC patents: US-6245064-B1 is rendered as `ATRIONIX INC` (co-assigned to The
  Regents of the University of California; cited by the US-8932208-B2 group and
  by VIVANT MEDICAL INC) and US-2006293730-A1 is rendered as `RUBINSKY BORIS`
  (co-assigned to UC; cited by FARAPULSE INC). The full text of US-6245064-B1
  contains no mention of California or the Regents, so the link cannot be
  recovered from unstructured fields either.
- Citing side. Original rows such as `MAQUET CARDIOVASCULAR LLC` and
  `CRYSTAL IS INC | H01L` are co-assignees of citing patents whose released
  rows render only one name (`KENDALE AMAR`, `SCHOWALTER LEO J`).
  `MAQUET CARDIOVASCULAR LLC` appears nowhere in any `Patents_info` string.

Since `validate.py` requires every ground-truth pair to appear in the answer,
no answer computed from the released databases could pass — consistent with the
observed 0/270 runs.

### Fix applied

`query3/ground_truth.csv` and the ground-truth list in `query3/validate.py`
were regenerated from the released data (the three pairs above). The validator
still only requires ground-truth pairs to be present, so answers that
additionally include near-miss pairs (e.g. CALIFORNIA INST OF TECHN via the
UNIV CALIFORNIA AT SAN DIEGO patent) continue to pass.

## Reproducing

```bash
# from the repository root, with both PATENTS database files in place
python failure_analysis/patents_query3/solve_query3.py
python failure_analysis/patents_query3/reproduce_query1_query2.py
```
