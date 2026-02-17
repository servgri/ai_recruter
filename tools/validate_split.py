"""
Regression validator: compares TaskExtractor output vs golden split in from_collegues/problem_split.csv.

Usage (from repo root):
  python tools/validate_split.py

By default it parses files from problem/original_files/<full_filename>.
"""

from __future__ import annotations

import argparse
import csv
import os
import sys
from dataclasses import dataclass
from typing import Dict, List, Tuple


REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from extractors import TaskExtractor  # noqa: E402
from utils import get_parser_for_file  # noqa: E402


def _norm(text: str) -> str:
    if not text:
        return ""
    return " ".join(str(text).replace("\r", " ").replace("\n", " ").split()).strip()


@dataclass(frozen=True)
class Case:
    full_filename: str
    expected: Dict[int, str]


def _load_golden_csv(path: str) -> List[Case]:
    cases: List[Case] = []
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            full_filename = (row.get("full_filename") or "").strip()
            if not full_filename:
                continue
            expected = {
                1: _norm(row.get("task_1", "")),
                2: _norm(row.get("task_2", "")),
                3: _norm(row.get("task_3", "")),
                4: _norm(row.get("task_4", "")),
            }
            cases.append(Case(full_filename=full_filename, expected=expected))
    return cases


def _parse_and_extract(file_path: str, extractor: TaskExtractor) -> Dict[int, str]:
    filename = os.path.basename(file_path)
    parser = get_parser_for_file(filename)
    if parser is None:
        raise RuntimeError(f"No parser for file: {filename}")

    content = parser.parse(file_path)
    tasks = extractor.extract_tasks(content)
    task_dict = {int(t.get("task_number", i + 1)): _norm(t.get("content", "")) for i, t in enumerate(tasks)}
    return {i: task_dict.get(i, "") for i in (1, 2, 3, 4)}


def _short_diff(a: str, b: str, limit: int = 220) -> Tuple[str, str]:
    def clip(s: str) -> str:
        if len(s) <= limit:
            return s
        return s[:limit] + "..."

    return clip(a), clip(b)


def main() -> int:
    ap = argparse.ArgumentParser(description="Validate TaskExtractor split vs golden CSV")
    ap.add_argument(
        "--golden",
        default=os.path.join(REPO_ROOT, "from_collegues", "problem_split.csv"),
        help="Path to golden problem_split.csv",
    )
    ap.add_argument(
        "--files-dir",
        default=os.path.join(REPO_ROOT, "problem", "original_files"),
        help="Directory with original files named as full_filename",
    )
    ap.add_argument("--limit", type=int, default=0, help="Limit number of cases (0 = all)")
    ap.add_argument("--only-mismatches", action="store_true", help="Print only mismatching files")
    args = ap.parse_args()

    cases = _load_golden_csv(args.golden)
    if args.limit and args.limit > 0:
        cases = cases[: args.limit]

    extractor = TaskExtractor()

    total = 0
    parsed = 0
    missing_file = 0
    exact_files = 0
    exact_tasks = 0
    total_tasks = 0

    for case in cases:
        total += 1
        file_path = os.path.join(args.files_dir, case.full_filename)
        if not os.path.exists(file_path):
            missing_file += 1
            if not args.only_mismatches:
                print(f"[MISSING] {case.full_filename} -> {file_path}")
            continue

        try:
            actual = _parse_and_extract(file_path, extractor)
            parsed += 1
        except Exception as e:
            if not args.only_mismatches:
                print(f"[ERROR] {case.full_filename}: {e}")
            continue

        # Compare
        file_ok = True
        for i in (1, 2, 3, 4):
            total_tasks += 1
            exp = case.expected.get(i, "")
            act = actual.get(i, "")
            if exp == act:
                exact_tasks += 1
            else:
                file_ok = False

        if file_ok:
            exact_files += 1
            if not args.only_mismatches:
                print(f"[OK] {case.full_filename}")
        else:
            print(f"[DIFF] {case.full_filename}")
            for i in (1, 2, 3, 4):
                exp = case.expected.get(i, "")
                act = actual.get(i, "")
                if exp != act:
                    exp_s, act_s = _short_diff(exp, act)
                    print(f"  task_{i}:")
                    print(f"    expected: {exp_s}")
                    print(f"    actual:   {act_s}")

    print("\n=== Summary ===")
    print(f"Cases in golden:        {len(cases)}")
    print(f"Files missing:          {missing_file}")
    print(f"Files parsed:           {parsed}")
    print(f"Files exact match:      {exact_files}/{parsed}")
    if total_tasks:
        print(f"Tasks exact match:      {exact_tasks}/{total_tasks} ({(exact_tasks/total_tasks)*100:.2f}%)")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

