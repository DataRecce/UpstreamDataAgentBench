"""Reproducible solver and analysis for PATENTS query3.

Implements the ground-truth join over the released DAB data:
citing.citation.publication_number == cited.publication_number,
cited assignee == 'UNIV CALIFORNIA', primary CPC (first=true) at
subclass level joined to cpc_definition.titleFull.

Run from the repository root:
    python failure_analysis/patents_query3/solve_query3.py
"""
import csv
import json
import re
import sqlite3
from collections import defaultdict
from pathlib import Path
from typing import Dict, Iterator, List, Optional, Set, Tuple

REPO_ROOT = Path(__file__).resolve().parents[2]
PUBLICATION_DB_PATH = REPO_ROOT / "query_PATENTS/query_dataset/patent_publication.db"
CPC_DUMP_PATH = REPO_ROOT / "query_PATENTS/query_dataset/patent_CPCDefinition.sql"
GROUND_TRUTH_PATH = REPO_ROOT / "query_PATENTS/query3/ground_truth.csv"
TARGET_ASSIGNEE = "UNIV CALIFORNIA"
PUBLICATION_NUMBER_PATTERN = re.compile(
    r"(?:publication|pub\.)\s*(?:number|no\.)\s*([A-Z]{2}-\w+-\w+)"
)
ASSIGNEE_PATTERNS = (
    re.compile(r"^(?P<assignee>.+?) holds? the "),
    re.compile(r" is (?:owned by|assigned to|held by|belonging to) (?P<assignee>.+?) and has "),
    re.compile(r", (?:owned by|assigned to|held by|belonging to) (?P<assignee>.+?), with "),
)


def load_cpc_subclass_titles(dump_path: Path) -> Dict[str, str]:
    """Parse the pg_dump COPY block into a {symbol: titleFull} mapping."""
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


def parse_patents_info(text: str) -> Tuple[Optional[str], Optional[str]]:
    """Extract (assignee, publication_number) from the natural-language summary."""
    assignee: Optional[str] = None
    for pattern in ASSIGNEE_PATTERNS:
        match = pattern.search(text)
        if match:
            assignee = match.group("assignee").strip()
            break
    if assignee == "[]":
        assignee = None
    publication_match = PUBLICATION_NUMBER_PATTERN.search(text)
    publication_number = publication_match.group(1) if publication_match else None
    return assignee, publication_number


def iterate_publications(cursor: sqlite3.Cursor) -> Iterator[Tuple[str, str, str, str]]:
    """Yield (Patents_info, inventor_harmonized, cpc, citation) rows."""
    yield from cursor.execute(
        "SELECT Patents_info, inventor_harmonized, cpc, citation FROM publicationinfo"
    )


def collect_uc_publication_numbers(cursor: sqlite3.Cursor) -> Set[str]:
    """Collect publication numbers of rows whose rendered assignee is exactly UNIV CALIFORNIA."""
    uc_publications: Set[str] = set()
    rows = cursor.execute(
        "SELECT Patents_info FROM publicationinfo WHERE Patents_info LIKE ?",
        (f"%{TARGET_ASSIGNEE}%",),
    )
    for (info,) in rows:
        assignee, publication_number = parse_patents_info(info)
        if assignee == TARGET_ASSIGNEE and publication_number:
            uc_publications.add(publication_number)
    return uc_publications


def extract_primary_subclasses(cpc_json: Optional[str]) -> Set[str]:
    """Return the CPC subclasses (first 4 chars) of all entries flagged first=true."""
    if not cpc_json:
        return set()
    try:
        entries = json.loads(cpc_json)
    except json.JSONDecodeError:
        return set()
    return {entry["code"][:4] for entry in entries if entry.get("first")}


def extract_cited_publications(citation_json: Optional[str]) -> Set[str]:
    """Return the publication numbers referenced in a citation JSON list."""
    if not citation_json:
        return set()
    try:
        entries = json.loads(citation_json)
    except json.JSONDecodeError:
        return set()
    return {
        entry["publication_number"]
        for entry in entries
        if entry.get("publication_number")
    }


def solve() -> Dict[str, Set[str]]:
    """Compute {citing_assignee: {primary CPC subclass titleFull}} from the released data."""
    subclass_titles = load_cpc_subclass_titles(CPC_DUMP_PATH)
    connection = sqlite3.connect(PUBLICATION_DB_PATH)
    cursor = connection.cursor()
    uc_publications = collect_uc_publication_numbers(cursor)
    results: Dict[str, Set[str]] = defaultdict(set)
    for info, inventors_json, cpc_json, citation_json in iterate_publications(cursor):
        cited_publications = extract_cited_publications(citation_json)
        if not (cited_publications & uc_publications):
            continue
        assignee, _ = parse_patents_info(info or "")
        if assignee is None or assignee == TARGET_ASSIGNEE:
            continue
        titles = {
            subclass_titles[subclass]
            for subclass in extract_primary_subclasses(cpc_json)
            if subclass in subclass_titles
        }
        results[assignee] |= titles
    connection.close()
    return results


def load_ground_truth(path: Path) -> List[Tuple[str, str]]:
    """Load the (citing_assignee, titleFull) pairs from ground_truth.csv."""
    with open(path, encoding="utf-8") as csv_file:
        return [
            (row["citing_assignee"], row["titleFull"])
            for row in csv.DictReader(csv_file)
        ]


def report_coverage(results: Dict[str, Set[str]]) -> None:
    """Print the derived answer and its coverage of the ground truth."""
    print("=== Answer derivable from the released data ===")
    for assignee in sorted(results):
        for title in sorted(results[assignee]):
            print(f"{assignee} | {title}")
    ground_truth = load_ground_truth(GROUND_TRUTH_PATH)
    covered = [
        (assignee, title)
        for assignee, title in ground_truth
        if title in results.get(assignee, set())
    ]
    print(f"\nGround-truth pairs covered: {len(covered)}/{len(ground_truth)}")
    for assignee, title in ground_truth:
        status = "COVERED" if (assignee, title) in covered else "MISSING"
        print(f"  {status}: {assignee} | {title[:70]}")


if __name__ == "__main__":
    report_coverage(solve())
