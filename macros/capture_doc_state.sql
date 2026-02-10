{% macro capture_doc_state() %}
    {#--
        Capture documentation changes from the dbt graph and insert only
        the diffs into the doc_changelog table.

        Usage:
            dbt run-operation capture_doc_state

        Reads from:  graph.nodes, graph.sources, doc_changelog table
        Writes to:   doc_changelog table (configured via vars)
    --#}

    {% if execute %}

        {#-- Step 1: Resolve the target table and ensure it exists --#}
        {% set changelog_rel = dbt_doc_tracker.get_changelog_relation() %}

        {{ log("dbt_doc_tracker: Creating doc_changelog table if not exists...", info=True) }}
        {% set create_sql %}
            {{ dbt_doc_tracker.create_changelog_table(changelog_rel) }}
        {% endset %}
        {% do run_query(create_sql) %}

        {#-- Step 2: Collect current documentation state from the graph --#}
        {% set current_entries = [] %}

        {#-- Models and Seeds --#}
        {% for node in graph.nodes.values() %}
            {% if node.resource_type in ['model', 'seed'] %}
                {% set entity_type = node.resource_type %}
                {% set entity_name = node.name %}

                {#-- Entity-level description --#}
                {% if node.description and node.description | trim | length > 0 %}
                    {% do current_entries.append({
                        'entity_type': entity_type,
                        'entity_name': entity_name,
                        'field_name': '__description__',
                        'description': node.description
                    }) %}
                {% endif %}

                {#-- Column-level descriptions --#}
                {% for col_name, col in node.columns.items() %}
                    {% if col.description and col.description | trim | length > 0 %}
                        {% do current_entries.append({
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
                {% do current_entries.append({
                    'entity_type': 'source',
                    'entity_name': entity_name,
                    'field_name': '__description__',
                    'description': source.description
                }) %}
            {% endif %}

            {#-- Source column descriptions --#}
            {% for col_name, col in source.columns.items() %}
                {% if col.description and col.description | trim | length > 0 %}
                    {% do current_entries.append({
                        'entity_type': 'source',
                        'entity_name': entity_name,
                        'field_name': col_name,
                        'description': col.description
                    }) %}
                {% endif %}
            {% endfor %}
        {% endfor %}

        {{ log("dbt_doc_tracker: Found " ~ current_entries | length ~ " documented items in graph", info=True) }}

        {#-- Step 3: Query the changelog for last known state --#}
        {% set last_known_state = {} %}

        {#-- Check if table has any data before querying --#}
        {% set table_exists = adapter.get_relation(
            database=changelog_rel.database,
            schema=changelog_rel.schema,
            identifier=changelog_rel.identifier
        ) %}

        {% if table_exists is not none %}
            {% set state_query %}
                WITH ranked AS (
                    SELECT
                        entity_type,
                        entity_name,
                        field_name,
                        change_type,
                        new_description,
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
                    change_type,
                    new_description
                FROM ranked
                WHERE rn = 1
            {% endset %}

            {% set results = run_query(state_query) %}

            {% if results and results.rows %}
                {% for row in results.rows %}
                    {% set key = row[0] ~ '|' ~ row[1] ~ '|' ~ row[2] %}
                    {% do last_known_state.update({
                        key: {
                            'change_type': row[3],
                            'new_description': row[4]
                        }
                    }) %}
                {% endfor %}
            {% endif %}

            {{ log("dbt_doc_tracker: Loaded " ~ last_known_state | length ~ " entries from last known state", info=True) }}
        {% else %}
            {{ log("dbt_doc_tracker: First run — no previous state found", info=True) }}
        {% endif %}

        {#-- Step 4: Compare current graph state vs last known state --#}
        {% set changes = [] %}
        {% set current_keys = {} %}

        {#-- Detect additions and modifications --#}
        {% for entry in current_entries %}
            {% set key = entry.entity_type ~ '|' ~ entry.entity_name ~ '|' ~ entry.field_name %}
            {% do current_keys.update({ key: true }) %}

            {% if key not in last_known_state %}
                {#-- Never seen before → added --#}
                {% do changes.append({
                    'entity_type': entry.entity_type,
                    'entity_name': entry.entity_name,
                    'field_name': entry.field_name,
                    'change_type': 'added',
                    'old_description': none,
                    'new_description': entry.description
                }) %}
            {% else %}
                {% set last = last_known_state[key] %}

                {% if last.change_type == 'removed' %}
                    {#-- Was previously removed, now back → added --#}
                    {% do changes.append({
                        'entity_type': entry.entity_type,
                        'entity_name': entry.entity_name,
                        'field_name': entry.field_name,
                        'change_type': 'added',
                        'old_description': none,
                        'new_description': entry.description
                    }) %}
                {% elif last.new_description != entry.description %}
                    {#-- Description changed → modified --#}
                    {% do changes.append({
                        'entity_type': entry.entity_type,
                        'entity_name': entry.entity_name,
                        'field_name': entry.field_name,
                        'change_type': 'modified',
                        'old_description': last.new_description,
                        'new_description': entry.description
                    }) %}
                {% endif %}
                {#-- else: no change, skip --#}
            {% endif %}
        {% endfor %}

        {#-- Detect removals --#}
        {% for key, last in last_known_state.items() %}
            {% if key not in current_keys and last.change_type != 'removed' %}
                {#-- Was present but is now gone → removed --#}
                {% set parts = key.split('|') %}
                {% do changes.append({
                    'entity_type': parts[0],
                    'entity_name': parts[1],
                    'field_name': parts[2],
                    'change_type': 'removed',
                    'old_description': last.new_description,
                    'new_description': none
                }) %}
            {% endif %}
        {% endfor %}

        {{ log("dbt_doc_tracker: Detected " ~ changes | length ~ " documentation changes", info=True) }}

        {#-- Step 5: Insert only the changes in batches --#}
        {% if changes | length > 0 %}

            {% set batch_size = 500 %}

            {% for batch_start in range(0, changes | length, batch_size) %}
                {% set batch_end = [batch_start + batch_size, changes | length] | min %}
                {% set batch = changes[batch_start:batch_end] %}

                {% set insert_sql %}
                    INSERT INTO {{ changelog_rel }}
                        (captured_at, entity_type, entity_name, field_name, change_type, old_description, new_description, invocation_id)
                    VALUES
                    {% for entry in batch %}
                        (
                            CURRENT_TIMESTAMP,
                            '{{ entry.entity_type }}',
                            '{{ dbt_doc_tracker.escape_single_quotes(entry.entity_name) }}',
                            '{{ dbt_doc_tracker.escape_single_quotes(entry.field_name) }}',
                            '{{ entry.change_type }}',
                            {% if entry.old_description is none %}
                                NULL,
                            {% else %}
                                '{{ dbt_doc_tracker.escape_single_quotes(entry.old_description) }}',
                            {% endif %}
                            {% if entry.new_description is none %}
                                NULL,
                            {% else %}
                                '{{ dbt_doc_tracker.escape_single_quotes(entry.new_description) }}',
                            {% endif %}
                            '{{ invocation_id }}'
                        )
                        {% if not loop.last %},{% endif %}
                    {% endfor %}
                {% endset %}
                {% do run_query(insert_sql) %}

                {{ log("dbt_doc_tracker: Inserted batch " ~ loop.index ~ " (" ~ batch | length ~ " changes)", info=True) }}
            {% endfor %}

            {#-- Explicitly commit — run-operation does not auto-commit --#}
            {% do adapter.commit() %}

            {{ log("dbt_doc_tracker: Complete. " ~ changes | length ~ " changes recorded.", info=True) }}
        {% else %}
            {{ log("dbt_doc_tracker: No documentation changes detected.", info=True) }}
        {% endif %}

    {% endif %}
{% endmacro %}
