select distinct store_id as store_key, store_region as region
from {{ ref('stg_transactions') }}
