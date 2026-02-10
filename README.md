# dbt Doc Tracker

A dbt package that detects and records documentation changes across your dbt project. Instead of storing full snapshots, it only records the diffs — when a description is added, modified, or removed. One lightweight table, minimal warehouse cost.

## The Problem

Documentation changes in dbt are invisible. When a column description changes, gets removed, or a new model goes undocumented, there's no built-in way to detect or track it. Git tracks source file changes, but it doesn't give you queryable, production-level visibility into what your documentation actually looks like over time.

## How It Works

```
dbt run-operation capture_doc_state
```

This macro reads every model, source, and seed description from dbt's compiled graph, compares it against the last known state in the `doc_changelog` table, and inserts only the changes. If nothing changed, nothing is written.

```
┌─────────────────────────────────────────────────────┐
│  dbt Project (YAML schemas + doc blocks)            │
│  ──► graph.nodes / graph.sources                    │
└──────────────────────┬──────────────────────────────┘
                       │ dbt run-operation capture_doc_state
                       ▼
┌─────────────────────────────────────────────────────┐
│  doc_changelog table (stores only changes)          │
└──────────────────────┬──────────────────────────────┘
                       │ dbt run --select dbt_doc_tracker
                       ▼
┌─────────────────────────────────────────────────────┐
│  doc_current_state  → current docs derived from     │
│                       changelog (view, zero storage) │
└─────────────────────────────────────────────────────┘
```

## Installation

Add to your `packages.yml`:

```yaml
packages:
  - git: "https://github.com/tripleaceme/dbt-doc-tracker.git"
    revision: v2.0.0
```

Then run:

```bash
dbt deps
```

## Configuration

By default, the package stores the `doc_changelog` table and views in your target database and schema. To use a custom location, add to your `dbt_project.yml`:

```yaml
vars:
  dbt_doc_tracker_database: "ANALYTICS"
  dbt_doc_tracker_schema: "DOC_TRACKING"
```

## Usage

### 1. Capture your current documentation state

```bash
dbt run-operation capture_doc_state
```

On the first run, this creates the `doc_changelog` table and records all documented items as `added`. On subsequent runs, it detects and records only the changes.

### 2. Build the current state view

```bash
dbt run --select dbt_doc_tracker
```

This creates:
- **`doc_current_state`** — a view showing the latest documentation for all entities, derived from the changelog

### 3. Query your documentation

```sql
-- See all documentation changes ever recorded
SELECT * FROM doc_changelog ORDER BY captured_at DESC;

-- See only the latest changes
SELECT *
FROM doc_changelog
WHERE captured_at = (SELECT MAX(captured_at) FROM doc_changelog);

-- See modifications (description text changed)
SELECT *
FROM doc_changelog
WHERE change_type = 'modified';

-- Audit current documentation coverage by resource type
SELECT
    entity_type,
    COUNT(*) AS documented_items
FROM doc_current_state
GROUP BY entity_type;
```

## Example

Suppose you have a model `fct_daily_sales` with this description:

```yaml
models:
  - name: fct_daily_sales
    description: "Daily sales aggregated from all transactions, Monday through Sunday, all hours"
    columns:
      - name: sale_date
        description: "The calendar date of aggregation. Covers all 7 days of the week."
```

You run `dbt run-operation capture_doc_state` to create the baseline. Both entries are recorded as `added`.

Later, a business requirement changes the scope:

```yaml
models:
  - name: fct_daily_sales
    description: "Daily sales from transactions, Monday through Friday, 10 AM to 10 PM"
    columns:
      - name: sale_date
        description: "The calendar date of aggregation. Weekdays only (Monday-Friday), business hours."
```

Run `dbt run-operation capture_doc_state` again, then query:

```sql
SELECT change_type, entity_name, field_name, old_description, new_description
FROM doc_changelog
WHERE change_type = 'modified';
```

| change_type | entity_name | field_name | old_description | new_description |
|---|---|---|---|---|
| modified | fct_daily_sales | \_\_description\_\_ | Daily sales aggregated from all transactions, Monday through Sunday, all hours | Daily sales from transactions, Monday through Friday, 10 AM to 10 PM |
| modified | fct_daily_sales | sale_date | The calendar date of aggregation. Covers all 7 days of the week. | The calendar date of aggregation. Weekdays only (Monday-Friday), business hours. |

## What Gets Tracked

The package captures descriptions from:

| Resource Type | Entity-Level Description | Column-Level Descriptions |
|---|---|---|
| **Models** | `models.name.description` | `models.name.columns.name.description` |
| **Sources** | `sources.tables.description` | `sources.tables.columns.name.description` |
| **Seeds** | `seeds.name.description` | `seeds.name.columns.name.description` |

Jinja `{{ doc('block_name') }}` references are automatically resolved by dbt before the macro reads them.

## Change Detection

| Scenario | Result |
|---|---|
| First run (empty table) | All documented items recorded as `added` |
| No changes since last run | Nothing written |
| Description text modified | `modified` row with old and new descriptions |
| Description removed or blanked | `removed` row |
| Previously removed, now re-added | `added` row |

## Automated Capture (Optional)

To automatically detect changes after every `dbt run`, add an `on-run-end` hook to your `dbt_project.yml`:

```yaml
on-run-end:
  - "{{ dbt_doc_tracker.capture_doc_state() }}"
```

## `doc_changelog` Table Schema

| Column | Type | Description |
|---|---|---|
| `captured_at` | TIMESTAMP | When the change was detected |
| `entity_type` | STRING | `model`, `source`, or `seed` |
| `entity_name` | STRING | Entity name (e.g., `fct_daily_sales` or `source_name.table_name`) |
| `field_name` | STRING | Column name, or `__description__` for entity-level docs |
| `change_type` | STRING | `added`, `modified`, or `removed` |
| `old_description` | STRING | Previous description (NULL for added entries) |
| `new_description` | STRING | Current description (NULL for removed entries) |
| `invocation_id` | STRING | dbt invocation ID for traceability |

## Migrating from v1.x

If upgrading from v1.x, you need to clean up the old objects:

1. Drop the old `doc_snapshots` table: `DROP TABLE IF EXISTS doc_snapshots;`
2. Drop the old `doc_changelog` view: `DROP VIEW IF EXISTS doc_changelog;`
3. Run `dbt run-operation capture_doc_state` to create the new `doc_changelog` table
4. Run `dbt run --select dbt_doc_tracker` to recreate the `doc_current_state` view

## Requirements

- dbt >= 1.6.0, < 2.0.0
- Any dbt-supported warehouse (Snowflake, BigQuery, Redshift, Postgres, Databricks)
