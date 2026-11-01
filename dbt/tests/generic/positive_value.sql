{# Custom generic test: every value must be strictly positive. #}
{% test positive_value(model, column_name) %}
select {{ column_name }}
from {{ model }}
where {{ column_name }} <= 0
{% endtest %}
