"""
Compare two DocState dictionaries and produce a list of typed change records.

Algorithm:
1. keys_prev = set of keys in previous snapshot
2. keys_curr = set of keys in current snapshot
3. ADDED   = keys_curr - keys_prev  (new documentation)
4. REMOVED = keys_prev - keys_curr  (deleted documentation)
5. For each key in (keys_prev & keys_curr):
       if prev[key] != curr[key] → MODIFIED
"""

from dataclasses import dataclass, asdict
from enum import Enum
from typing import Dict, List, Optional


class ChangeType(str, Enum):
    ADDED = "added"
    REMOVED = "removed"
    MODIFIED = "modified"


@dataclass
class ChangeRecord:
    change_type: ChangeType
    doc_key: str  # e.g. "model.fct_daily_sales.sale_date"
    entity_type: str  # "model", "source", "seed"
    entity_name: str  # "fct_daily_sales"
    field: str  # "sale_date" or "__description__"
    old_value: Optional[str]
    new_value: Optional[str]

    @property
    def is_model_description(self) -> bool:
        return self.field == "__description__"

    def to_dict(self) -> dict:
        d = asdict(self)
        d["change_type"] = self.change_type.value
        return d


def detect_changes(
    prev_state: Dict[str, str],
    curr_state: Dict[str, str],
) -> List[ChangeRecord]:
    """Compare two doc states and return list of changes."""
    changes: List[ChangeRecord] = []

    prev_keys = set(prev_state.keys())
    curr_keys = set(curr_state.keys())

    # Added entries
    for key in sorted(curr_keys - prev_keys):
        parts = _parse_key(key)
        changes.append(
            ChangeRecord(
                change_type=ChangeType.ADDED,
                doc_key=key,
                old_value=None,
                new_value=curr_state[key],
                **parts,
            )
        )

    # Removed entries
    for key in sorted(prev_keys - curr_keys):
        parts = _parse_key(key)
        changes.append(
            ChangeRecord(
                change_type=ChangeType.REMOVED,
                doc_key=key,
                old_value=prev_state[key],
                new_value=None,
                **parts,
            )
        )

    # Modified entries
    for key in sorted(prev_keys & curr_keys):
        if prev_state[key] != curr_state[key]:
            parts = _parse_key(key)
            changes.append(
                ChangeRecord(
                    change_type=ChangeType.MODIFIED,
                    doc_key=key,
                    old_value=prev_state[key],
                    new_value=curr_state[key],
                    **parts,
                )
            )

    return changes


def _parse_key(key: str) -> dict:
    """
    Parse doc key into entity components.

    Examples:
        "model.fct_daily_sales.sale_date"
            → entity_type="model", entity_name="fct_daily_sales", field="sale_date"
        "source.hoodie_sales.orders.order_id"
            → entity_type="source", entity_name="hoodie_sales.orders", field="order_id"
        "model.fct_daily_sales.__description__"
            → entity_type="model", entity_name="fct_daily_sales", field="__description__"
    """
    parts = key.split(".")
    if parts[0] == "source":
        # source.{source_name}.{table_name}.{field}
        return {
            "entity_type": "source",
            "entity_name": f"{parts[1]}.{parts[2]}" if len(parts) > 2 else parts[1],
            "field": parts[3] if len(parts) > 3 else "__description__",
        }
    else:
        # model.{name}.{field} or seed.{name}.{field}
        return {
            "entity_type": parts[0],
            "entity_name": parts[1] if len(parts) > 1 else "unknown",
            "field": parts[2] if len(parts) > 2 else "__description__",
        }
