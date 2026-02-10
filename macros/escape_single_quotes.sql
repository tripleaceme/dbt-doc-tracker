{% macro escape_single_quotes(value) %}
    {#-- Escape single quotes for safe SQL string insertion --#}
    {{ return(value | replace("'", "''")) }}
{% endmacro %}
