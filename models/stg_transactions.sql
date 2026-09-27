select
    line_id,
    cast(order_date as date) as order_date,
    store_id,
    store_region,
    product_id,
    product_name,
    category,
    cast(quantity as integer) as quantity,
    cast(unit_price_usd as numeric(12, 2)) as unit_price_usd,
    cast(discount_pct as numeric(5, 2)) as discount_pct
from {{ ref('transactions') }}
