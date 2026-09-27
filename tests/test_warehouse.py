from pathlib import Path

import duckdb
import pytest

from warehouse import build_warehouse, generate_transactions


def test_generated_transactions_are_repeatable_and_have_unique_grain():
    first = generate_transactions(240, seed=17)
    second = generate_transactions(240, seed=17)
    assert first == second
    assert len(first) == len({row["line_id"] for row in first}) == 240
    assert all(row["quantity"] > 0 and row["unit_price_usd"] > 0 for row in first)


def test_star_schema_reconciles_source_sales_and_is_idempotent(tmp_path: Path):
    rows = generate_transactions(240, seed=17)
    db_path = tmp_path / "retail.duckdb"
    first = build_warehouse(db_path, rows)
    second = build_warehouse(db_path, rows)
    assert second == first
    assert first["source_lines"] == first["fact_lines"] == 240
    assert first["sales_difference_usd"] == 0
    with duckdb.connect(str(db_path), read_only=True) as db:
        assert db.execute("select count(*) from dim_product").fetchone()[0] > 1
        assert db.execute("select count(*) from dim_store").fetchone()[0] > 1
        assert db.execute("select count(*) from fact_sales where date_key is null or product_key is null or store_key is null").fetchone()[0] == 0


def test_duplicate_source_line_is_rejected(tmp_path: Path):
    rows = generate_transactions(3, seed=1)
    with pytest.raises(ValueError, match="line_id"):
        build_warehouse(tmp_path / "retail.duckdb", rows + [rows[0]])
