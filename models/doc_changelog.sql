{{
  config(
    materialized='view'
  )
}}

{#--
    Documentation Changelog: compares the latest 2 snapshots and shows
    all documentation changes (added / modified / removed).

    The doc_snapshots table is managed by the capture_doc_state macro.
    Query this view after running: dbt run-operation capture_doc_state
--#}

{% set snapshot_rel = dbt_doc_tracker.get_snapshot_relation() %}

WITH snapshot_ids AS (
    SELECT DISTINCT
        snapshot_id,
        MIN(captured_at) AS captured_at
    FROM {{ snapshot_rel }}
    GROUP BY snapshot_id
),

ranked AS (
    SELECT
        snapshot_id,
        captured_at,
        DENSE_RANK() OVER (ORDER BY captured_at DESC) AS snapshot_rank
    FROM snapshot_ids
),

latest AS (
    SELECT snapshot_id FROM ranked WHERE snapshot_rank = 1
),

previous AS (
    SELECT snapshot_id FROM ranked WHERE snapshot_rank = 2
),

current_state AS (
    SELECT
        s.entity_type,
        s.entity_name,
        s.field_name,
        s.description,
        s.snapshot_id,
        s.captured_at
    FROM {{ snapshot_rel }} s
    INNER JOIN latest l ON s.snapshot_id = l.snapshot_id
),

previous_state AS (
    SELECT
        s.entity_type,
        s.entity_name,
        s.field_name,
        s.description,
        s.snapshot_id,
        s.captured_at
    FROM {{ snapshot_rel }} s
    INNER JOIN previous p ON s.snapshot_id = p.snapshot_id
),

changes AS (
    SELECT
        CASE
            WHEN p.entity_name IS NULL THEN 'added'
            WHEN c.entity_name IS NULL THEN 'removed'
            ELSE 'modified'
        END AS change_type,
        COALESCE(c.entity_type, p.entity_type) AS entity_type,
        COALESCE(c.entity_name, p.entity_name) AS entity_name,
        COALESCE(c.field_name, p.field_name) AS field_name,
        p.description AS old_description,
        c.description AS new_description,
        c.snapshot_id AS current_snapshot_id,
        p.snapshot_id AS previous_snapshot_id,
        COALESCE(c.captured_at, p.captured_at) AS captured_at
    FROM current_state c
    FULL OUTER JOIN previous_state p
        ON c.entity_type = p.entity_type
        AND c.entity_name = p.entity_name
        AND c.field_name = p.field_name
    WHERE
        p.entity_name IS NULL
        OR c.entity_name IS NULL
        OR p.description != c.description
)

SELECT * FROM changes
ORDER BY change_type, entity_type, entity_name, field_name
