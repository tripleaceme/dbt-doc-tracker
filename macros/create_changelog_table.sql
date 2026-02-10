{% macro create_changelog_table(relation) %}
    {#--
        Creates the doc_changelog table if it does not exist.
        Uses dbt cross-database type macros for portability.
    --#}

    CREATE TABLE IF NOT EXISTS {{ relation }} (
        captured_at       {{ dbt.type_timestamp() }},
        entity_type       {{ dbt.type_string() }},
        entity_name       {{ dbt.type_string() }},
        field_name        {{ dbt.type_string() }},
        change_type       {{ dbt.type_string() }},
        old_description   {{ dbt.type_string() }},
        new_description   {{ dbt.type_string() }},
        invocation_id     {{ dbt.type_string() }}
    )
{% endmacro %}
