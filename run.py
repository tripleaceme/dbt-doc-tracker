#!/usr/bin/env python3
"""
dbt Documentation Version Tracker - CLI Entry Point
====================================================

Usage:
    python run.py                        # Run full pipeline
    python run.py --snapshot-only        # Only take snapshot, no publish
    python run.py --dry-run              # Detect changes, print, don't publish
    python run.py --config path/to.yml   # Custom config file
    python run.py --list-snapshots       # List all available snapshots
"""

import argparse
import sys
import yaml

from dbt_doc_tracker.yaml_parser import parse_dbt_project
from dbt_doc_tracker.snapshot_manager import save_snapshot, load_latest_snapshot, list_snapshots
from dbt_doc_tracker.change_detector import detect_changes
from dbt_doc_tracker.changelog_builder import (
    build_changelog_entry,
    save_changelog,
    format_changelog_text,
)
from dbt_doc_tracker.confluence_publisher import ConfluencePublisher


def main():
    parser = argparse.ArgumentParser(
        description="dbt Documentation Version Tracker",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run.py --dry-run                 # Parse docs, detect changes, print results
  python run.py --snapshot-only           # Take a baseline snapshot only
  python run.py --list-snapshots          # Show all stored snapshots
  python run.py --config my_config.yml    # Use a custom config file
        """,
    )
    parser.add_argument(
        "--config", default="config.yml", help="Path to config file (default: config.yml)"
    )
    parser.add_argument(
        "--snapshot-only",
        action="store_true",
        help="Only take a snapshot, don't compare or publish",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Detect and print changes, but don't publish to Confluence",
    )
    parser.add_argument(
        "--list-snapshots",
        action="store_true",
        help="List all available snapshots and exit",
    )
    args = parser.parse_args()

    # Load config
    try:
        with open(args.config) as f:
            config = yaml.safe_load(f)
    except FileNotFoundError:
        print(f"Error: Config file '{args.config}' not found.")
        sys.exit(1)

    # List snapshots mode
    if args.list_snapshots:
        snapshots = list_snapshots(config)
        if not snapshots:
            print("No snapshots found.")
        else:
            print(f"Found {len(snapshots)} snapshot(s):\n")
            for snap in snapshots:
                print(
                    f"  {snap['snapshot_id']}  |  {snap['total_documented_items']} items  |  "
                    f"commit: {snap.get('git_commit_sha', 'unknown')}  |  "
                    f"branch: {snap.get('git_branch', 'unknown')}"
                )
        return

    # Step 1: Parse current documentation state
    print(f"Parsing dbt project: {config['dbt_project_path']}")
    current_state = parse_dbt_project(config["dbt_project_path"], config)
    print(f"  Found {len(current_state)} documented items")

    if len(current_state) == 0:
        print("  Warning: No documentation found. Check your config paths.")
        return

    # Step 2: Load previous snapshot
    previous = load_latest_snapshot(config)

    # Step 3: Save current snapshot
    snapshot_path = save_snapshot(current_state, config)
    print(f"  Snapshot saved: {snapshot_path}")

    if args.snapshot_only:
        print("\nSnapshot-only mode. Done.")
        return

    # Step 4: Detect changes
    if previous is None:
        print("\n  No previous snapshot found. This is the baseline (first run).")
        print("  Run again after making documentation changes to see the diff.")
        return

    prev_metadata, prev_state = previous
    changes = detect_changes(prev_state, current_state)

    if not changes:
        print("\n  No documentation changes detected since last snapshot.")
        return

    # Step 5: Build and display changelog
    metadata = {
        "snapshot_id": snapshot_path.split("/")[-1].replace(".json", ""),
        "timestamp": prev_metadata.get("timestamp", ""),
        "git_commit_sha": prev_metadata.get("git_commit_sha", "unknown"),
    }
    entry = build_changelog_entry(changes, metadata)

    print(f"\n  Detected {len(changes)} documentation change(s):\n")
    print(format_changelog_text(entry))

    # Step 6: Save changelog
    changelog_path = save_changelog(entry, config)
    print(f"  Changelog updated: {changelog_path}")

    if args.dry_run:
        print("\n  Dry-run mode. Skipping Confluence publish.")
        return

    # Step 7: Publish to Confluence
    try:
        publisher = ConfluencePublisher(config)
        publisher.publish([entry])
        print("  Published to Confluence successfully.")
    except Exception as e:
        print(f"\n  Warning: Confluence publish failed: {e}")
        print("  The changelog was saved locally. You can retry publishing later.")


if __name__ == "__main__":
    main()
