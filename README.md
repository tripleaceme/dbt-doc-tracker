# dbt Doc Tracker

A dbt package that tracks documentation changes across your dbt project over time. Every time you capture a snapshot, the package records all model, source, and seed descriptions into a warehouse table. SQL views then surface what changed between snapshots — so you always have a versioned history of your documentation.

## The Problem

When a column description changes from *"Daily sales, Monday through Sunday"* to *"Daily sales, Monday through Friday, 10 AM to 10 PM"*, there's no built-in way in dbt to see what it used to say. A new team member joining months later has no visibility into how or why documentation evolved.

## How It Works

```
dbt run-operation capture_doc_state
```

This macro reads every model, source, and seed description from dbt's compiled graph and inserts them into a `doc_snapshots` table in your warehouse. Run it again after making documentation changes, and the `doc_changelog` view will show you exactly what changed.

```
┌─────────────────────────────────────────────────────┐
│  dbt Project (YAML schemas + doc blocks)            │
│  ──► graph.nodes / graph.sources                    │
└──────────────────────┬──────────────────────────────┘
                       │ dbt run-operation capture_doc_state
                       ▼
┌─────────────────────────────────────────────────────┐
│  doc_snapshots table (append-only, in your warehouse)│
└──────────────────────┬──────────────────────────────┘
                       │ dbt run --select dbt_doc_tracker
                       ▼
┌─────────────────────────────────────────────────────┐
│  doc_changelog      → diff of latest 2 snapshots    │
│  doc_current_state  → latest snapshot only           │
└─────────────────────────────────────────────────────┘
```

## Installation

Add to your `packages.yml`:

```yaml
packages:
  - git: "https://github.com/tripleaceme/dbt-doc-tracker.git"
    revision: v1.0.0
```

Then run:

```bash
dbt deps
```

## Configuration

By default, the package stores the `doc_snapshots` table and views in your target database and schema. To use a custom location, add to your `dbt_project.yml`:

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

This creates the `doc_snapshots` table (if it doesn't exist) and inserts all current documentation as a new snapshot batch.

### 2. Build the changelog views

```bash
dbt run --select dbt_doc_tracker
```

This creates two views:
- **`doc_changelog`** — shows differences between the two most recent snapshots
- **`doc_current_state`** — shows the latest documentation snapshot

### 3. Query your documentation changes

```sql
-- See all changes between the last two snapshots
SELECT * FROM doc_changelog;

-- See only modifications (description text changed)
SELECT *
FROM doc_changelog
WHERE change_type = 'modified';

-- See newly added documentation
SELECT *
FROM doc_changelog
WHERE change_type = 'added';

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

You run `dbt run-operation capture_doc_state` to create the baseline.

Later, a business requirement changes the scope to weekdays and business hours only:

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
FROM doc_changelog;
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

## Automated Capture (Optional)

To automatically capture a snapshot after every `dbt run`, add an `on-run-end` hook to your `dbt_project.yml`:

```yaml
on-run-end:
  - "{{ dbt_doc_tracker.capture_doc_state() }}"
```

## `doc_snapshots` Table Schema

| Column | Type | Description |
|---|---|---|
| `snapshot_id` | STRING | Batch ID per capture run (timestamp-based) |
| `captured_at` | TIMESTAMP | When the snapshot was taken |
| `entity_type` | STRING | `model`, `source`, or `seed` |
| `entity_name` | STRING | Entity name (e.g., `fct_daily_sales` or `source_name.table_name`) |
| `field_name` | STRING | Column name, or `__description__` for entity-level docs |
| `description` | STRING | The documentation text |
| `invocation_id` | STRING | dbt invocation ID for traceability |

## Requirements

- dbt >= 1.6.0, < 2.0.0
- Any dbt-supported warehouse (Snowflake, BigQuery, Redshift, Postgres, Databricks)
