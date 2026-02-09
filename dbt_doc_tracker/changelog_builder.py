"""
Build structured changelog entries from change records and append
to a cumulative changelog JSON file.
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import List


def build_changelog_entry(changes: list, metadata: dict) -> dict:
    """
    Build a single changelog entry from a list of ChangeRecord objects.

    Args:
        changes: List of ChangeRecord objects from change_detector
        metadata: Snapshot metadata dict with snapshot_id, timestamp, git_commit_sha
    """
    summary = {"added": 0, "removed": 0, "modified": 0}
    for c in changes:
        summary[c.change_type.value] += 1
    summary["total"] = len(changes)

    return {
        "version": metadata.get("snapshot_id", datetime.now(timezone.utc).strftime("%Y-%m-%d_%H%M%S")),
        "timestamp": metadata.get("timestamp", datetime.now(timezone.utc).isoformat()),
        "git_commit": metadata.get("git_commit_sha", "unknown"),
        "summary": summary,
        "changes": [c.to_dict() for c in changes],
    }


def save_changelog(entry: dict, config: dict) -> str:
    """
    Append a changelog entry to the cumulative changelog.json file.
    Returns the changelog file path.
    """
    changelog_dir = Path(config["changelog_dir"])
    changelog_dir.mkdir(parents=True, exist_ok=True)
    filepath = changelog_dir / "changelog.json"

    if filepath.exists():
        with open(filepath) as f:
            data = json.load(f)
    else:
        data = {"entries": []}

    # Newest first
    data["entries"].insert(0, entry)

    with open(filepath, "w") as f:
        json.dump(data, f, indent=2)

    return str(filepath)


def format_changelog_text(entry: dict) -> str:
    """
    Format a changelog entry as human-readable text for console output.
    """
    lines = []
    s = entry["summary"]
    lines.append(
        f"Version: {entry['version']} | Commit: {entry['git_commit']} | "
        f"{entry['timestamp']}"
    )
    lines.append(
        f"Summary: {s['added']} added, {s['modified']} modified, "
        f"{s['removed']} removed ({s['total']} total changes)"
    )
    lines.append("-" * 70)

    for change in entry["changes"]:
        change_type = change["change_type"].upper()
        entity = f"{change['entity_type']}.{change['entity_name']}"
        field = "Model Description" if change["field"] == "__description__" else change["field"]

        lines.append(f"  [{change_type}] {entity} → {field}")
        if change.get("old_value"):
            lines.append(f"    Old: {change['old_value']}")
        if change.get("new_value"):
            lines.append(f"    New: {change['new_value']}")
        lines.append("")

    return "\n".join(lines)
