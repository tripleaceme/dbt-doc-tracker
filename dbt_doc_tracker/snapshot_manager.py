"""
Save and load documentation state snapshots as timestamped JSON files.

Each snapshot captures the full documentation state at a point in time,
along with metadata (timestamp, git commit, item count).
"""

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional, Tuple


def save_snapshot(doc_state: Dict[str, str], config: dict) -> str:
    """
    Save current doc state as a timestamped JSON file.
    Returns the snapshot file path.
    """
    snapshot_dir = Path(config["snapshot_dir"])
    snapshot_dir.mkdir(parents=True, exist_ok=True)

    now = datetime.now(timezone.utc)
    snapshot_id = now.strftime("%Y-%m-%d_%H%M%S")

    snapshot = {
        "metadata": {
            "snapshot_id": snapshot_id,
            "timestamp": now.isoformat(),
            "dbt_project_path": config.get("dbt_project_path", "unknown"),
            "git_commit_sha": _get_git_sha(config.get("dbt_project_path", ".")),
            "git_branch": _get_git_branch(config.get("dbt_project_path", ".")),
            "total_documented_items": len(doc_state),
        },
        "doc_state": doc_state,
    }

    filepath = snapshot_dir / f"{snapshot_id}.json"
    with open(filepath, "w") as f:
        json.dump(snapshot, f, indent=2, sort_keys=True)

    return str(filepath)


def load_latest_snapshot(config: dict) -> Optional[Tuple[dict, Dict[str, str]]]:
    """
    Load the most recent snapshot.
    Returns (metadata, doc_state) or None if no snapshots exist.
    """
    snapshot_dir = Path(config["snapshot_dir"])
    if not snapshot_dir.exists():
        return None

    files = sorted(snapshot_dir.glob("*.json"), reverse=True)
    if not files:
        return None

    with open(files[0]) as f:
        data = json.load(f)

    return data["metadata"], data["doc_state"]


def load_snapshot_by_id(snapshot_id: str, config: dict) -> Optional[Tuple[dict, Dict[str, str]]]:
    """Load a specific snapshot by its ID (filename without .json)."""
    snapshot_dir = Path(config["snapshot_dir"])
    filepath = snapshot_dir / f"{snapshot_id}.json"

    if not filepath.exists():
        return None

    with open(filepath) as f:
        data = json.load(f)

    return data["metadata"], data["doc_state"]


def list_snapshots(config: dict) -> list:
    """List all available snapshots, newest first."""
    snapshot_dir = Path(config["snapshot_dir"])
    if not snapshot_dir.exists():
        return []

    snapshots = []
    for filepath in sorted(snapshot_dir.glob("*.json"), reverse=True):
        with open(filepath) as f:
            data = json.load(f)
        snapshots.append(data["metadata"])

    return snapshots


def _get_git_sha(project_path: str) -> str:
    """Get the current git commit SHA (short form)."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=project_path,
            capture_output=True,
            text=True,
        )
        return result.stdout.strip()[:8] if result.returncode == 0 else "unknown"
    except Exception:
        return "unknown"


def _get_git_branch(project_path: str) -> str:
    """Get the current git branch name."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=project_path,
            capture_output=True,
            text=True,
        )
        return result.stdout.strip() if result.returncode == 0 else "unknown"
    except Exception:
        return "unknown"
