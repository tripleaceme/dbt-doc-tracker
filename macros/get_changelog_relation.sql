{% macro get_changelog_relation() %}
    {#--
        Returns the fully-qualified relation for the doc_changelog table.
        Respects user-configured database/schema via vars,
        or defaults to target.database / target.schema.
    --#}

    {% set db = var('dbt_doc_tracker_database', target.database) %}
    {% set schema = var('dbt_doc_tracker_schema', target.schema) %}

    {#-- Handle null vars (default values) --#}
    {% if db is none %}
        {% set db = target.database %}
    {% endif %}
    {% if schema is none %}
        {% set schema = target.schema %}
    {% endif %}

    {% set relation = adapter.get_relation(
        database=db,
        schema=schema,
        identifier='doc_changelog'
    ) %}

    {#-- If table doesn't exist yet, create a reference to it --#}
    {% if relation is none %}
        {% set relation = api.Relation.create(
            database=db,
            schema=schema,
            identifier='doc_changelog'
        ) %}
    {% endif %}

    {{ return(relation) }}
{% endmacro %}
