"""Deterministic retail source data and an offline, reconciled star schema."""

from __future__ import annotations

import argparse
import csv
import json
import random
from datetime import date, timedelta
from pathlib import Path

import duckdb
import pandas as pd


PRODUCTS = (
    ("P01", "Headphones", "Electronics", 49.90),
    ("P02", "Keyboard", "Electronics", 79.00),
    ("P03", "Coffee beans", "Grocery", 16.50),
    ("P04", "Notebook", "Stationery", 8.75),
    ("P05", "Desk lamp", "Home", 35.00),
)
STORES = (("S01", "North"), ("S02", "South"), ("S03", "West"))
FIELDS = (
    "line_id", "order_date", "store_id", "store_region", "product_id",
    "product_name", "category", "quantity", "unit_price_usd", "discount_pct",
)


def generate_transactions(count: int, seed: int = 20260927) -> list[dict]:
    if count < 1:
        raise ValueError("count must be positive")
    rng = random.Random(seed)
    rows = []
    for index in range(count):
        product_id, name, category, price = rng.choice(PRODUCTS)
        store_id, region = rng.choice(STORES)
        rows.append({
            "line_id": f"L{index + 1:05d}",
            "order_date": (date(2026, 1, 1) + timedelta(days=rng.randrange(90))).isoformat(),
            "store_id": store_id,
            "store_region": region,
            "product_id": product_id,
            "product_name": name,
            "category": category,
            "quantity": rng.randint(1, 5),
            "unit_price_usd": price,
            "discount_pct": rng.choice((0.0, 0.05, 0.10)),
        })
    return rows


def build_warehouse(db_path: str | Path, rows: list[dict]) -> dict:
    """Replace the local warehouse atomically and reconcile at source-line grain."""
    ids = [str(row["line_id"]) for row in rows]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate line_id in source")
    if not rows:
        raise ValueError("source must contain at least one line_id")
    frame = pd.DataFrame(rows, columns=FIELDS)
    if frame.isna().any().any() or (frame["quantity"] <= 0).any():
        raise ValueError("source has null or nonpositive values")
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with duckdb.connect(str(path)) as db:
        db.register("incoming", frame)
        db.execute("BEGIN TRANSACTION")
        try:
            db.execute("CREATE OR REPLACE TABLE source_transactions AS SELECT * FROM incoming")
            db.execute("""
                CREATE OR REPLACE TABLE dim_date AS
                SELECT DISTINCT CAST(replace(order_date, '-', '') AS INTEGER) AS date_key,
                       CAST(order_date AS DATE) AS calendar_date,
                       year(CAST(order_date AS DATE)) AS year,
                       month(CAST(order_date AS DATE)) AS month
                FROM source_transactions
            """)
            db.execute("""
                CREATE OR REPLACE TABLE dim_store AS
                SELECT DISTINCT store_id AS store_key, store_region AS region
                FROM source_transactions
            """)
            db.execute("""
                CREATE OR REPLACE TABLE dim_product AS
                SELECT DISTINCT product_id AS product_key, product_name, category
                FROM source_transactions
            """)
            db.execute("""
                CREATE OR REPLACE TABLE fact_sales AS
                SELECT line_id,
                       CAST(replace(order_date, '-', '') AS INTEGER) AS date_key,
                       store_id AS store_key,
                       product_id AS product_key,
                       CAST(quantity AS INTEGER) AS quantity,
                       CAST(round(quantity * unit_price_usd * (1 - discount_pct), 2) AS DECIMAL(14,2)) AS sales_usd
                FROM source_transactions
            """)
            source_lines, source_sales = db.execute("""
                SELECT count(*), CAST(sum(round(quantity * unit_price_usd * (1 - discount_pct), 2)) AS DECIMAL(14,2))
                FROM source_transactions
            """).fetchone()
            fact_lines, fact_sales = db.execute("SELECT count(*), sum(sales_usd) FROM fact_sales").fetchone()
            missing_keys = db.execute("""
                SELECT count(*) FROM fact_sales f
                LEFT JOIN dim_date d USING (date_key)
                LEFT JOIN dim_store s USING (store_key)
                LEFT JOIN dim_product p USING (product_key)
                WHERE d.date_key IS NULL OR s.store_key IS NULL OR p.product_key IS NULL
            """).fetchone()[0]
            if source_lines != fact_lines or source_sales != fact_sales or missing_keys:
                raise ValueError("star schema reconciliation failed")
            db.execute("COMMIT")
        except Exception:
            db.execute("ROLLBACK")
            raise
    return {
        "source_lines": source_lines,
        "fact_lines": fact_lines,
        "source_sales_usd": float(source_sales),
        "fact_sales_usd": float(fact_sales),
        "sales_difference_usd": float(source_sales - fact_sales),
        "missing_dimension_keys": missing_keys,
    }


def export_source(path: str | Path, rows: list[dict]) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--count", type=int, default=600)
    parser.add_argument("--db", type=Path, default=Path("artifacts/retail.duckdb"))
    args = parser.parse_args()
    source = generate_transactions(args.count)
    export_source("seeds/transactions.csv", source)
    summary = build_warehouse(args.db, source)
    Path("artifacts").mkdir(exist_ok=True)
    Path("artifacts/summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
