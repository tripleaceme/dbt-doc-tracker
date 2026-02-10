{% macro capture_doc_state() %}
    {#--
        Capture all documentation from the dbt graph and insert it
        as a new snapshot batch into the doc_snapshots table.

        Usage:
            dbt run-operation capture_doc_state

        Reads from:  graph.nodes, graph.sources
        Writes to:   doc_snapshots table (configured via vars)
    --#}

    {% if execute %}

        {#-- Step 1: Resolve the target table and ensure it exists --#}
        {% set snapshot_rel = dbt_doc_tracker.get_snapshot_relation() %}

        {{ log("dbt_doc_tracker: Creating doc_snapshots table if not exists...", info=True) }}
        {% set create_sql %}
            {{ dbt_doc_tracker.create_snapshot_table(snapshot_rel) }}
        {% endset %}
        {% do run_query(create_sql) %}

        {#-- Step 2: Generate a snapshot batch ID --#}
        {% set snapshot_id = modules.datetime.datetime.utcnow().strftime('%Y-%m-%d_%H%M%S') %}
        {{ log("dbt_doc_tracker: Snapshot ID = " ~ snapshot_id, info=True) }}

        {#-- Step 3: Collect all documentation entries from the graph --#}
        {% set entries = [] %}

        {#-- Models and Seeds --#}
        {% for node in graph.nodes.values() %}
            {% if node.resource_type in ['model', 'seed'] %}
                {% set entity_type = node.resource_type %}
                {% set entity_name = node.name %}

                {#-- Entity-level description --#}
                {% if node.description and node.description | trim | length > 0 %}
                    {% do entries.append({
                        'entity_type': entity_type,
                        'entity_name': entity_name,
                        'field_name': '__description__',
                        'description': node.description
                    }) %}
                {% endif %}

                {#-- Column-level descriptions --#}
                {% for col_name, col in node.columns.items() %}
                    {% if col.description and col.description | trim | length > 0 %}
                        {% do entries.append({
                            'entity_type': entity_type,
                            'entity_name': entity_name,
                            'field_name': col_name,
                            'description': col.description
                        }) %}
                    {% endif %}
                {% endfor %}
            {% endif %}
        {% endfor %}

        {#-- Sources --#}
        {% for source in graph.sources.values() %}
            {% set entity_name = source.source_name ~ '.' ~ source.name %}

            {#-- Source table description --#}
            {% if source.description and source.description | trim | length > 0 %}
                {% do entries.append({
                    'entity_type': 'source',
                    'entity_name': entity_name,
                    'field_name': '__description__',
                    'description': source.description
                }) %}
            {% endif %}

            {#-- Source column descriptions --#}
            {% for col_name, col in source.columns.items() %}
                {% if col.description and col.description | trim | length > 0 %}
                    {% do entries.append({
                        'entity_type': 'source',
                        'entity_name': entity_name,
                        'field_name': col_name,
                        'description': col.description
                    }) %}
                {% endif %}
            {% endfor %}
        {% endfor %}

        {{ log("dbt_doc_tracker: Found " ~ entries | length ~ " documented items", info=True) }}

        {#-- Step 4: Insert all entries in batches --#}
        {% if entries | length > 0 %}

            {% set batch_size = 500 %}

            {% for batch_start in range(0, entries | length, batch_size) %}
                {% set batch_end = [batch_start + batch_size, entries | length] | min %}
                {% set batch = entries[batch_start:batch_end] %}

                {% set insert_sql %}
                    INSERT INTO {{ snapshot_rel }}
                        (snapshot_id, captured_at, entity_type, entity_name, field_name, description, invocation_id)
                    VALUES
                    {% for entry in batch %}
                        (
                            '{{ snapshot_id }}',
                            CURRENT_TIMESTAMP,
                            '{{ entry.entity_type }}',
                            '{{ dbt_doc_tracker.escape_single_quotes(entry.entity_name) }}',
                            '{{ dbt_doc_tracker.escape_single_quotes(entry.field_name) }}',
                            '{{ dbt_doc_tracker.escape_single_quotes(entry.description) }}',
                            '{{ invocation_id }}'
                        )
                        {% if not loop.last %},{% endif %}
                    {% endfor %}
                {% endset %}
                {% do run_query(insert_sql) %}

                {{ log("dbt_doc_tracker: Inserted batch " ~ loop.index ~ " (" ~ batch | length ~ " rows)", info=True) }}
            {% endfor %}

            {{ log("dbt_doc_tracker: Snapshot complete. " ~ entries | length ~ " entries captured.", info=True) }}
        {% else %}
            {{ log("dbt_doc_tracker: No documented items found. Check your schema YAML files.", info=True) }}
        {% endif %}

    {% endif %}
{% endmacro %}
