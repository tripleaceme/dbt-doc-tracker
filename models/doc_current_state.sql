{{
  config(
    materialized='view'
  )
}}

{#--
    Current Documentation State: shows the latest snapshot only.
    Useful for auditing documentation coverage across your dbt project.
--#}

{% set snapshot_rel = dbt_doc_tracker.get_snapshot_relation() %}

WITH latest_snapshot AS (
    SELECT snapshot_id
    FROM {{ snapshot_rel }}
    ORDER BY captured_at DESC
    LIMIT 1
)

SELECT
    s.snapshot_id,
    s.captured_at,
    s.entity_type,
    s.entity_name,
    s.field_name,
    s.description,
    s.invocation_id
FROM {{ snapshot_rel }} s
INNER JOIN latest_snapshot ls ON s.snapshot_id = ls.snapshot_id
ORDER BY s.entity_type, s.entity_name, s.field_name
