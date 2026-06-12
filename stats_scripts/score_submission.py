#!/usr/bin/env python3
"""
Score a submission JSON against the repo's validators and print Pass@1.

A submission is a JSON list of entries:
    {"dataset": <name>, "query": <id>, "run": <run id>, "answer": <str>}

For every query folder query_<DATASET>/query<N> that exists in the repo, the
script computes Pass@1 = (#passing runs) / RUNS_PER_QUERY. Missing queries or
runs and empty answers count as failures. Two overall aggregations are
reported:
  - pooled:     mean of Pass@1 over all queries (all datasets pooled)
  - by_dataset: mean over datasets of (mean Pass@1 over the dataset's queries)

Usage:
    python stats_scripts/score_submission.py submissions/react_gpt-5.2.json \
        [--repo-root /workspace] [--workers 4] [--runs-per-query 50] \
        [--validators-override PATENTS=/tmp/old_patents] [--json out.json] \
        [--no-accel]

--validators-override lets you score with an alternate set of validate.py
files for one dataset (e.g. validators extracted from another git revision);
the directory must contain query<N>/validate.py subfolders.

If the `rapidfuzz` package is available, the pure-Python Levenshtein in
common_scaffold is transparently replaced with rapidfuzz's implementation
(verified to return identical distances); disable with --no-accel.
"""

import argparse
import importlib.util
import json
import sys
from collections import defaultdict
from multiprocessing import Pool
from pathlib import Path

# Maps submission dataset names (including lowercase promptql-style names)
# to query folder names. Datasets not listed map to query_<name as-is>.
DATASET_FOLDER_MAP = {
    "DEPS_DEV_V1": "query_DEPS_DEV_V1",
    "GITHUB_REPOS": "query_GITHUB_REPOS",
    "PANCANCER_ATLAS": "query_PANCANCER_ATLAS",
    "PATENTS": "query_PATENTS",
    "music_brainz_20k": "query_music_brainz_20k",
    "deps_dev": "query_DEPS_DEV_V1",
    "github_repos": "query_GITHUB_REPOS",
    "pancancer": "query_PANCANCER_ATLAS",
    "patents": "query_PATENTS",
    "music_brainz": "query_music_brainz_20k",
}

# Canonical dataset key per query folder, so promptql/react names merge.
FOLDER_CANONICAL = {v: v[len("query_"):] for v in DATASET_FOLDER_MAP.values()}


def dataset_folder(name: str) -> str:
    return DATASET_FOLDER_MAP.get(name, f"query_{name}")


def discover_queries(repo_root: Path, dataset_folders):
    """Return {folder_name: sorted list of query ids (str)} for existing folders."""
    queries = {}
    for folder in dataset_folders:
        base = repo_root / folder
        if not base.is_dir():
            continue
        qids = []
        for sub in base.iterdir():
            if sub.is_dir() and sub.name.startswith("query") and sub.name[5:].isdigit():
                if (sub / "validate.py").exists():
                    qids.append(sub.name[5:])
        if qids:
            queries[folder] = sorted(qids, key=int)
    return queries


# ---------------------------------------------------------------------------
# Worker process
# ---------------------------------------------------------------------------

_VALIDATOR_CACHE = {}
_REPO_ROOT = None


def _maybe_accelerate_levenshtein(repo_root: str, accel: bool):
    """Swap common_scaffold's pure-Python levenshtein for rapidfuzz (identical
    results, orders of magnitude faster for the sliding-window validators)."""
    if not accel:
        return
    try:
        from rapidfuzz.distance import Levenshtein as _RL
        import common_scaffold.validate.levenshtein as _lev_mod
        _lev_mod.levenshtein = lambda s1, s2: _RL.distance(s1, s2)
    except ImportError:
        pass


def _init_worker(repo_root: str, accel: bool):
    global _REPO_ROOT
    _REPO_ROOT = repo_root
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)
    _maybe_accelerate_levenshtein(repo_root, accel)


def _load_validator(validate_py: str):
    mod = _VALIDATOR_CACHE.get(validate_py)
    if mod is None:
        spec = importlib.util.spec_from_file_location(
            f"validator_{len(_VALIDATOR_CACHE)}", validate_py)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        _VALIDATOR_CACHE[validate_py] = mod
    return mod


def _validate_one(task):
    """task = (key, validate_py_path, answer) -> (key, passed)"""
    key, validate_py, answer = task
    if not answer:
        return key, False
    try:
        mod = _load_validator(validate_py)
        ok, _reason = mod.validate(answer)
        return key, bool(ok)
    except Exception:
        return key, False


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

def build_tasks(entries, repo_root: Path, queries, overrides):
    """Build validation tasks for entries belonging to known queries.

    Returns (tasks, seen) where tasks are (key, validate_py, answer) with
    key = (folder, qid, run). Duplicate (folder, qid, run) keeps first entry.
    """
    tasks, seen = [], set()
    for e in entries:
        folder = dataset_folder(str(e["dataset"]))
        qid = str(e["query"])
        if folder not in queries or qid not in queries[folder]:
            continue
        key = (folder, qid, str(e["run"]))
        if key in seen:
            continue
        seen.add(key)
        base = Path(overrides[folder]) if folder in overrides else repo_root / folder
        validate_py = str(base / f"query{qid}" / "validate.py")
        tasks.append((key, validate_py, e.get("answer") or ""))
    return tasks


def run_validations(tasks, repo_root: Path, workers: int, accel: bool,
                    progress_every: int = 100, label: str = ""):
    results = {}
    if not tasks:
        return results
    with Pool(workers, initializer=_init_worker,
              initargs=(str(repo_root), accel)) as pool:
        for n, (key, passed) in enumerate(
                pool.imap_unordered(_validate_one, tasks, chunksize=8), 1):
            results[key] = passed
            if n % progress_every == 0 or n == len(tasks):
                print(f"  [{label}] validated {n}/{len(tasks)}", flush=True)
    return results


def aggregate(results, queries, runs_per_query):
    """Compute Pass@1 per query/dataset and both overall aggregations.

    runs_per_query = 0 means "auto": each query's denominator is the number of
    distinct runs present for it (queries with no runs score 0). Use this for
    submissions with a variable number of trials per query.
    """
    pass_counts = defaultdict(int)
    run_counts = defaultdict(int)
    for (folder, qid, _run), passed in results.items():
        run_counts[(folder, qid)] += 1
        if passed:
            pass_counts[(folder, qid)] += 1

    per_query = {}      # (folder, qid) -> pass@1
    per_dataset = {}    # canonical dataset name -> mean pass@1 over queries
    for folder, qids in queries.items():
        ds = FOLDER_CANONICAL.get(folder, folder[len("query_"):])
        vals = []
        for qid in qids:
            denom = runs_per_query or run_counts.get((folder, qid), 0)
            p = pass_counts.get((folder, qid), 0) / denom if denom else 0.0
            per_query[(folder, qid)] = p
            vals.append(p)
        per_dataset[ds] = sum(vals) / len(vals)

    pooled = sum(per_query.values()) / len(per_query) if per_query else 0.0
    by_dataset = (sum(per_dataset.values()) / len(per_dataset)
                  if per_dataset else 0.0)
    return {
        "per_query": {f"{f}/query{q}": v for (f, q), v in sorted(per_query.items())},
        "per_dataset": dict(sorted(per_dataset.items())),
        "pooled": pooled,
        "by_dataset": by_dataset,
        "pass_counts": {f"{f}/query{q}": c for (f, q), c in sorted(pass_counts.items())},
    }


def score_submission(submission_path, repo_root, workers=4, runs_per_query=50,
                     overrides=None, accel=True):
    repo_root = Path(repo_root)
    overrides = overrides or {}
    entries = json.loads(Path(submission_path).read_text())

    folders = sorted({dataset_folder(str(e["dataset"])) for e in entries})
    queries = discover_queries(repo_root, folders)

    tasks = build_tasks(entries, repo_root, queries, overrides)
    results = run_validations(tasks, repo_root, workers, accel,
                              label=Path(submission_path).name)
    return aggregate(results, queries, runs_per_query)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("submission", help="path to submission JSON")
    ap.add_argument("--repo-root", default=str(Path(__file__).resolve().parents[1]))
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--runs-per-query", type=int, default=50)
    ap.add_argument("--validators-override", action="append", default=[],
                    metavar="DATASET=DIR",
                    help="use validators from DIR for DATASET (repeatable)")
    ap.add_argument("--json", help="optionally also write full results to this path")
    ap.add_argument("--no-accel", action="store_true",
                    help="do not substitute rapidfuzz for the pure-Python levenshtein")
    args = ap.parse_args()

    overrides = {}
    for spec in args.validators_override:
        name, _, path = spec.partition("=")
        overrides[dataset_folder(name)] = path

    res = score_submission(args.submission, args.repo_root, args.workers,
                           args.runs_per_query, overrides,
                           accel=not args.no_accel)

    print(f"\n=== {args.submission} ===")
    print("Pass@1 per dataset:")
    for ds, v in res["per_dataset"].items():
        print(f"  {ds:20s} {v:.4f}")
    print(f"Overall (pooled over all queries):       {res['pooled']:.4f}")
    print(f"Overall (mean of dataset means):         {res['by_dataset']:.4f}")

    if args.json:
        Path(args.json).write_text(json.dumps(res, indent=2))
        print(f"Full results written to {args.json}")


if __name__ == "__main__":
    main()
