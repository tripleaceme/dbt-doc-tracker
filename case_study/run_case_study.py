#!/usr/bin/env python3
"""
Case Study: RetailCo fct_daily_sales Documentation Evolution
============================================================

Demonstrates the documentation versioning pipeline by running through
3 versions of the fct_daily_sales model:

  V1 (Initial):  Monday-Sunday, all hours
  V2 (Change 1): Monday-Friday, all hours (weekends removed)
  V3 (Change 2): Monday-Friday, 10 AM-10 PM (time filter added)

Run from the project root:
    python case_study/run_case_study.py
"""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dbt_doc_tracker.yaml_parser import parse_single_yaml
from dbt_doc_tracker.change_detector import detect_changes
from dbt_doc_tracker.changelog_builder import build_changelog_entry, format_changelog_text

CASE_STUDY_DIR = os.path.dirname(os.path.abspath(__file__))


def main():
    # Parse each version
    v1 = parse_single_yaml(os.path.join(CASE_STUDY_DIR, "fct_daily_sales_v1.yml"))
    v2 = parse_single_yaml(os.path.join(CASE_STUDY_DIR, "fct_daily_sales_v2.yml"))
    v3 = parse_single_yaml(os.path.join(CASE_STUDY_DIR, "fct_daily_sales_v3.yml"))

    print("=" * 70)
    print("CASE STUDY: RetailCo fct_daily_sales Documentation Evolution")
    print("=" * 70)

    # Show V1 baseline
    print(f"\nV1 Baseline: {len(v1)} documented items")
    for key, value in sorted(v1.items()):
        print(f"  {key}: {value}")

    # V1 → V2: Business removes weekends
    print("\n" + "=" * 70)
    print("TRANSITION: V1 → V2 (Business removes Saturday & Sunday)")
    print("=" * 70)

    changes_v1_v2 = detect_changes(v1, v2)
    entry_v1_v2 = build_changelog_entry(
        changes_v1_v2,
        {"snapshot_id": "v2_weekdays_only", "timestamp": "2026-01-15T10:00:00Z", "git_commit_sha": "abc123"},
    )
    print(format_changelog_text(entry_v1_v2))

    # V2 → V3: Business adds time filter
    print("=" * 70)
    print("TRANSITION: V2 → V3 (Business adds 10 AM - 10 PM filter)")
    print("=" * 70)

    changes_v2_v3 = detect_changes(v2, v3)
    entry_v2_v3 = build_changelog_entry(
        changes_v2_v3,
        {"snapshot_id": "v3_business_hours", "timestamp": "2026-02-01T14:30:00Z", "git_commit_sha": "def456"},
    )
    print(format_changelog_text(entry_v2_v3))

    # Full history: V1 → V3
    print("=" * 70)
    print("FULL HISTORY: V1 → V3 (all changes from initial to current)")
    print("=" * 70)

    changes_v1_v3 = detect_changes(v1, v3)
    entry_v1_v3 = build_changelog_entry(
        changes_v1_v3,
        {"snapshot_id": "v3_full_diff", "timestamp": "2026-02-01T14:30:00Z", "git_commit_sha": "def456"},
    )
    print(format_changelog_text(entry_v1_v3))

    print("=" * 70)
    print("CASE STUDY COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    main()
