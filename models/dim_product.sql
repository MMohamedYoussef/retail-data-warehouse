select distinct product_id as product_key, product_name, category
from {{ ref('stg_transactions') }}
