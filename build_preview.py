"""Render a static warehouse scorecard from the fact and dimension tables."""

from pathlib import Path

import duckdb
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


DB = Path("artifacts/retail.duckdb")
OUT = Path("assets/warehouse-preview.png")

with duckdb.connect(str(DB), read_only=True) as db:
    total, lines = db.execute("select sum(sales_usd), count(*) from fact_sales").fetchone()
    regions = db.execute("""
        select s.region, sum(f.sales_usd) as sales
        from fact_sales f join dim_store s on f.store_key = s.store_key
        group by 1 order by 2 desc
    """).fetchall()
    categories = db.execute("""
        select p.category, sum(f.sales_usd) as sales
        from fact_sales f join dim_product p on f.product_key = p.product_key
        group by 1 order by 2 desc
    """).fetchall()

fig = plt.figure(figsize=(12, 7), facecolor="#101a2b")
fig.text(.06, .92, "RETAIL | WAREHOUSE", fontsize=14, weight="bold", color="#67e8f9")
fig.text(.06, .83, "Sales model health", fontsize=28, weight="bold", color="white")
fig.text(.06, .73, f"${total:,.0f}", fontsize=27, weight="bold", color="white")
fig.text(.06, .67, "Net sales", fontsize=11, color="#9fb2cb")
fig.text(.37, .73, f"{lines:,}", fontsize=27, weight="bold", color="white")
fig.text(.37, .67, "Fact rows", fontsize=11, color="#9fb2cb")
fig.text(.65, .73, "$0.00", fontsize=27, weight="bold", color="#67e8f9")
fig.text(.65, .67, "Source reconciliation gap", fontsize=11, color="#9fb2cb")
for position, title, values, color in (
    ([.06, .15, .40, .39], "Sales by region", regions, "#67e8f9"),
    ([.55, .15, .40, .39], "Sales by category", categories, "#a78bfa"),
):
    ax = fig.add_axes(position, facecolor="#17243a")
    labels = [row[0] for row in values][::-1]
    amounts = [float(row[1]) for row in values][::-1]
    bars = ax.barh(labels, amounts, color=color, height=.55)
    ax.bar_label(bars, labels=[f"${v:,.0f}" for v in amounts], padding=4, color="white", fontsize=9)
    ax.set_xlim(0, max(amounts) * 1.32)
    ax.set_title(title, loc="left", pad=18, color="white", fontsize=13, weight="bold")
    ax.tick_params(axis="y", colors="#d4e1f2", length=0, labelsize=10)
    ax.tick_params(axis="x", bottom=False, labelbottom=False)
    for spine in ax.spines.values():
        spine.set_visible(False)
fig.text(.06, .06, "Synthetic transactions • DuckDB star schema • fixed seed", color="#7890ad", fontsize=9)
OUT.parent.mkdir(exist_ok=True)
fig.savefig(OUT, dpi=150, facecolor=fig.get_facecolor())
plt.close(fig)
print(OUT)
