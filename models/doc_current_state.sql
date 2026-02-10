{{
  config(
    materialized='view'
  )
}}

{#--
    Current Documentation State: derives the latest known state
    from the doc_changelog table. Shows only entities that are
    currently documented (excludes removed entries).
--#}

{% set changelog_rel = dbt_doc_tracker.get_changelog_relation() %}

WITH ranked AS (
    SELECT
        entity_type,
        entity_name,
        field_name,
        change_type,
        new_description AS description,
        captured_at,
        invocation_id,
        ROW_NUMBER() OVER (
            PARTITION BY entity_type, entity_name, field_name
            ORDER BY captured_at DESC
        ) AS rn
    FROM {{ changelog_rel }}
)

SELECT
    entity_type,
    entity_name,
    field_name,
    description,
    captured_at,
    invocation_id
FROM ranked
WHERE rn = 1
  AND change_type != 'removed'
ORDER BY entity_type, entity_name, field_name
