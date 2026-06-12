"""Reproduce PATENTS query1 and query2 ground truths from the released data.

The recipe shared by both queries:
- one count per CPC entry flagged first=true (duplicates included, as released);
- filing year extracted from the natural-language filing_date;
- EMA over the years present for each group (no zero-filling of gap years),
  seeded with the first year's count;
- best year = argmax of the EMA series.

Run from the repository root:
    python failure_analysis/patents_query3/reproduce_query1_query2.py
"""
import csv
import json
import re
import sqlite3
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parents[2]
PUBLICATION_DB_PATH = REPO_ROOT / "query_PATENTS/query_dataset/patent_publication.db"
CPC_DUMP_PATH = REPO_ROOT / "query_PATENTS/query_dataset/patent_CPCDefinition.sql"
YEAR_PATTERN = re.compile(r"(1[789]\d\d|20\d\d)")
PUBLICATION_COUNTRY_PATTERN = re.compile(
    r"(?:publication|pub\.)\s*(?:number|no\.)\s*([A-Z]{2})-"
)
MONTH_NUMBERS = {
    month: index + 1
    for index, month in enumerate(
        ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]
    )
}


def extract_year(text: Optional[str]) -> Optional[int]:
    match = YEAR_PATTERN.search(text or "")
    return int(match.group(1)) if match else None


def extract_month(text: Optional[str]) -> Optional[int]:
    lowered = (text or "").lower()
    return next((num for name, num in MONTH_NUMBERS.items() if name in lowered), None)


def extract_first_cpc_groups(cpc_json: Optional[str], prefix_length: int) -> List[str]:
    if not cpc_json:
        return []
    try:
        entries = json.loads(cpc_json)
    except json.JSONDecodeError:
        return []
    return [
        entry["code"][:prefix_length]
        for entry in entries
        if entry.get("first") and entry.get("code")
    ]


def compute_best_years(
    counts_by_group: Dict[str, Dict[int, int]], smoothing_factor: float
) -> Dict[str, int]:
    """Best (argmax-EMA) year per group, EMA over years present only, seeded at zero."""
    best_years: Dict[str, int] = {}
    for group, counts in counts_by_group.items():
        ema = 0.0
        best_value: Optional[float] = None
        for year in sorted(counts):
            ema = smoothing_factor * counts[year] + (1 - smoothing_factor) * ema
            if best_value is None or ema > best_value:
                best_value = ema
                best_years[group] = year
    return best_years


def load_cpc_subclass_titles(dump_path: Path) -> Dict[str, str]:
    titles: Dict[str, str] = {}
    is_in_copy_block = False
    with open(dump_path, encoding="utf-8") as dump_file:
        for line in dump_file:
            if line.startswith("COPY public.cpc_definition"):
                is_in_copy_block = True
                continue
            if not is_in_copy_block:
                continue
            if line.startswith("\\."):
                break
            fields = line.rstrip("\n").split("\t")
            if len(fields) >= 21:
                titles[fields[18]] = fields[20]
    return titles


def reproduce_query1(cursor: sqlite3.Cursor) -> List[str]:
    """Level-5 (subclass) groups whose EMA(0.2) of filings peaks in 2022."""
    counts: Dict[str, Dict[int, int]] = defaultdict(lambda: defaultdict(int))
    for filing_date, cpc_json in cursor.execute(
        "SELECT filing_date, cpc FROM publicationinfo"
    ):
        year = extract_year(filing_date)
        if year is None:
            continue
        for group in extract_first_cpc_groups(cpc_json, prefix_length=4):
            counts[group][year] += 1
    best_years = compute_best_years(counts, smoothing_factor=0.2)
    return sorted(group for group, year in best_years.items() if year == 2022)


def reproduce_query2(cursor: sqlite3.Cursor) -> List[Tuple[str, str, int]]:
    """Level-4 (class) EMA(0.1) best years for DE patents granted in H2 2019."""
    counts: Dict[str, Dict[int, int]] = defaultdict(lambda: defaultdict(int))
    for info, filing_date, grant_date, cpc_json in cursor.execute(
        "SELECT Patents_info, filing_date, grant_date, cpc FROM publicationinfo"
    ):
        country_match = PUBLICATION_COUNTRY_PATTERN.search(info or "")
        if not country_match or country_match.group(1) != "DE":
            continue
        if extract_year(grant_date) != 2019 or (extract_month(grant_date) or 0) < 7:
            continue
        filing_year = extract_year(filing_date)
        if filing_year is None:
            continue
        for group in extract_first_cpc_groups(cpc_json, prefix_length=3):
            counts[group][filing_year] += 1
    best_years = compute_best_years(counts, smoothing_factor=0.1)
    titles = load_cpc_subclass_titles(CPC_DUMP_PATH)
    return sorted(
        (titles.get(group, group), group, year) for group, year in best_years.items()
    )


def diff_query1(derived: List[str]) -> None:
    with open(REPO_ROOT / "query_PATENTS/query1/ground_truth.csv") as csv_file:
        expected = {line.strip() for line in csv_file} - {"cpc_group", ""}
    print(f"query1: derived {len(derived)} groups, ground truth {len(expected)}")
    print("  missing from derived:", sorted(expected - set(derived)))
    print("  extra in derived:", sorted(set(derived) - expected))


def diff_query2(derived: List[Tuple[str, str, int]]) -> None:
    with open(REPO_ROOT / "query_PATENTS/query2/ground_truth.csv") as csv_file:
        expected = {
            (row["titleFull"], row["cpc_group"], int(row["best_year"]))
            for row in csv.DictReader(csv_file)
        }
    print(f"query2: derived {len(derived)} groups, ground truth {len(expected)}")
    print("  missing from derived:", sorted(expected - set(derived)))
    extra = sorted(set(derived) - expected)
    print(f"  derived rows not in ground truth: {len(extra)}")
    for title, group, year in extra:
        print(f"    {group} {year} {title[:60]}")


if __name__ == "__main__":
    connection = sqlite3.connect(PUBLICATION_DB_PATH)
    cursor = connection.cursor()
    diff_query1(reproduce_query1(cursor))
    diff_query2(reproduce_query2(cursor))
    connection.close()
