with source_total as (
    select count(*) as lines,
           sum(round(quantity * unit_price_usd * (1 - discount_pct), 2)) as sales
    from {{ ref('stg_transactions') }}
), fact_total as (
    select count(*) as lines, sum(sales_usd) as sales
    from {{ ref('fact_sales') }}
)
select 1 as mismatch
from source_total s cross join fact_total f
where s.lines <> f.lines or abs(s.sales - f.sales) > 0.01
