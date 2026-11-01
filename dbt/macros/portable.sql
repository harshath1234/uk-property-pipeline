{#
  Adapter-specific SQL lives here so the models stay identical on DuckDB and
  BigQuery. Each macro branches on target.type.
#}

{# Use the custom schema name as-is (e.g. "marts"), not "<target>_marts". #}
{% macro generate_schema_name(custom_schema_name, node) -%}
  {%- if custom_schema_name is none -%}{{ target.schema }}{%- else -%}{{ custom_schema_name | trim }}{%- endif -%}
{%- endmacro %}

{% macro surrogate_key(cols) -%}
  {%- set parts = [] -%}
  {%- for c in cols -%}
    {%- do parts.append("coalesce(cast(" ~ c ~ " as " ~ dbt.type_string() ~ "), '~')") -%}
  {%- endfor -%}
  {%- if target.type == 'bigquery' -%}
    to_hex(md5(concat({{ parts | join(", '|', ") }})))
  {%- else -%}
    md5(concat({{ parts | join(", '|', ") }}))
  {%- endif -%}
{%- endmacro %}

{% macro median(col) -%}
  {%- if target.type == 'bigquery' -%}
    approx_quantiles({{ col }}, 100)[offset(50)]
  {%- else -%}
    median({{ col }})
  {%- endif -%}
{%- endmacro %}

{% macro date_spine(start_date_sql, end_date_sql) -%}
  {%- if target.type == 'bigquery' -%}
    select d as date_day
    from unnest(generate_date_array({{ start_date_sql }}, {{ end_date_sql }})) as d
  {%- else -%}
    select cast(d as date) as date_day
    from generate_series(cast({{ start_date_sql }} as timestamp),
                         cast({{ end_date_sql }} as timestamp), interval 1 day) as t(d)
  {%- endif -%}
{%- endmacro %}

{% macro date_key(col) -%}
  cast(extract(year from {{ col }}) * 10000 + extract(month from {{ col }}) * 100
       + extract(day from {{ col }}) as {{ dbt.type_int() }})
{%- endmacro %}
