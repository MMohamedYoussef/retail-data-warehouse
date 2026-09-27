select distinct
    cast(to_char(order_date, 'YYYYMMDD') as integer) as date_key,
    order_date as calendar_date,
    extract(year from order_date)::integer as year,
    extract(month from order_date)::integer as month
from {{ ref('stg_transactions') }}
