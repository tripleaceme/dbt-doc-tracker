"""
Parse dbt YAML schema files and extract all documentation into a flat dictionary.

Handles:
- models: block (model-level and column-level descriptions)
- sources: block (source → table → column descriptions)
- seeds: block (seed-level and column-level descriptions)
- Jinja doc block references: {{ doc('block_name') }}
- Doc block .md files: {% docs block_name %} ... {% enddocs %}
"""

import re
import yaml
from pathlib import Path
from typing import Dict

# Type alias: documentation state is a flat dict of key → description
DocState = Dict[str, str]

# Regex to detect {{ doc('name') }} or {{ doc("name") }} references
DOC_REF_PATTERN = re.compile(r"\{\{\s*doc\(['\"](\w+)['\"]\)\s*\}\}")

# Regex to extract {% docs name %} ... {% enddocs %} blocks from .md files
DOC_BLOCK_PATTERN = re.compile(
    r"\{%\s*docs\s+(\w+)\s*%\}(.*?)\{%\s*enddocs\s*%\}",
    re.DOTALL,
)


def parse_dbt_project(project_path: str, config: dict) -> DocState:
    """
    Walk the dbt project, parse all schema YAMLs, return flat doc state.

    Returns dict like:
        {
            "model.fct_daily_sales.__description__": "Daily sales from...",
            "model.fct_daily_sales.sale_date": "The calendar date of...",
            "source.hoodie_sales.orders.__description__": "Orders placed by...",
            "source.hoodie_sales.orders.order_id": "Primary key for orders.",
        }
    """
    doc_blocks = _load_doc_blocks(project_path, config)
    doc_state: DocState = {}

    schema_files = _find_schema_files(project_path, config)
    for filepath in schema_files:
        try:
            with open(filepath) as f:
                data = yaml.safe_load(f)
        except (yaml.YAMLError, OSError):
            continue

        if not isinstance(data, dict):
            continue

        # Parse models block
        for model in data.get("models", []):
            if isinstance(model, dict):
                _extract_model_docs(model, doc_blocks, doc_state, prefix="model")

        # Parse sources block
        for source in data.get("sources", []):
            if isinstance(source, dict):
                source_name = source.get("name", "unknown")
                for table in source.get("tables", []):
                    if isinstance(table, dict):
                        _extract_source_docs(source_name, table, doc_blocks, doc_state)

        # Parse seeds block
        for seed in data.get("seeds", []):
            if isinstance(seed, dict):
                _extract_model_docs(seed, doc_blocks, doc_state, prefix="seed")

    return doc_state


def parse_single_yaml(filepath: str) -> DocState:
    """
    Parse a single YAML file into DocState format.
    Convenience function for case study and testing.
    """
    with open(filepath) as f:
        data = yaml.safe_load(f)

    if not isinstance(data, dict):
        return {}

    doc_state: DocState = {}

    for model in data.get("models", []):
        if isinstance(model, dict):
            _extract_model_docs(model, {}, doc_state, prefix="model")

    for source in data.get("sources", []):
        if isinstance(source, dict):
            source_name = source.get("name", "unknown")
            for table in source.get("tables", []):
                if isinstance(table, dict):
                    _extract_source_docs(source_name, table, {}, doc_state)

    for seed in data.get("seeds", []):
        if isinstance(seed, dict):
            _extract_model_docs(seed, {}, doc_state, prefix="seed")

    return doc_state


def _extract_model_docs(
    model: dict, doc_blocks: dict, state: DocState, prefix: str
) -> None:
    """Extract documentation from a model/seed entry."""
    name = model.get("name", "unknown")
    desc = model.get("description", "")
    desc = _resolve_doc_ref(desc, doc_blocks)
    if desc:
        state[f"{prefix}.{name}.__description__"] = desc

    for col in model.get("columns", []):
        if not isinstance(col, dict):
            continue
        col_name = col.get("name", "unknown")
        col_desc = col.get("description", "")
        col_desc = _resolve_doc_ref(col_desc, doc_blocks)
        if col_desc:
            state[f"{prefix}.{name}.{col_name}"] = col_desc


def _extract_source_docs(
    source_name: str, table: dict, doc_blocks: dict, state: DocState
) -> None:
    """Extract documentation from a source table entry."""
    table_name = table.get("name", "unknown")
    desc = table.get("description", "")
    desc = _resolve_doc_ref(desc, doc_blocks)
    if desc:
        state[f"source.{source_name}.{table_name}.__description__"] = desc

    for col in table.get("columns", []):
        if not isinstance(col, dict):
            continue
        col_name = col.get("name", "unknown")
        col_desc = col.get("description", "")
        col_desc = _resolve_doc_ref(col_desc, doc_blocks)
        if col_desc:
            state[f"source.{source_name}.{table_name}.{col_name}"] = col_desc


def _resolve_doc_ref(text: str, doc_blocks: dict) -> str:
    """Replace {{ doc('name') }} with actual content from .md files."""
    if not text:
        return text
    match = DOC_REF_PATTERN.search(text)
    if match:
        block_name = match.group(1)
        return doc_blocks.get(block_name, text)
    return text


def _load_doc_blocks(project_path: str, config: dict) -> dict:
    """
    Parse all .md files containing {% docs name %} ... {% enddocs %} blocks.
    Returns dict: {"order_status": "The status of the order..."}
    """
    blocks = {}
    exclude_dirs = config.get("exclude_dirs", [])

    for pattern in config.get("doc_block_patterns", []):
        for md_path in Path(project_path).glob(pattern):
            if any(excl in str(md_path) for excl in exclude_dirs):
                continue
            try:
                content = md_path.read_text()
            except OSError:
                continue
            for match in DOC_BLOCK_PATTERN.finditer(content):
                blocks[match.group(1)] = match.group(2).strip()

    return blocks


def _find_schema_files(project_path: str, config: dict) -> list:
    """Find all YAML schema files, excluding dbt_packages, target, etc."""
    files = []
    exclude_dirs = config.get("exclude_dirs", [])

    for pattern in config.get("schema_patterns", ["**/*.yml"]):
        for path in Path(project_path).glob(pattern):
            if any(excl in str(path) for excl in exclude_dirs):
                continue
            files.append(str(path))

    return sorted(files)
