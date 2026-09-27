select
    line_id,
    cast(to_char(order_date, 'YYYYMMDD') as integer) as date_key,
    store_id as store_key,
    product_id as product_key,
    quantity,
    round(quantity * unit_price_usd * (1 - discount_pct), 2) as sales_usd
from {{ ref('stg_transactions') }}
