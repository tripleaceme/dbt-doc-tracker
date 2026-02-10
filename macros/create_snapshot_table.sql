{% macro create_snapshot_table(relation) %}
    {#--
        Creates the doc_snapshots table if it does not exist.
        Uses dbt cross-database type macros for portability.
    --#}

    CREATE TABLE IF NOT EXISTS {{ relation }} (
        snapshot_id     {{ dbt.type_string() }},
        captured_at     {{ dbt.type_timestamp() }},
        entity_type     {{ dbt.type_string() }},
        entity_name     {{ dbt.type_string() }},
        field_name      {{ dbt.type_string() }},
        description     {{ dbt.type_string() }},
        invocation_id   {{ dbt.type_string() }}
    )
{% endmacro %}
