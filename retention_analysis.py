# Ecommerce customer retention and cohort analysis
# Install once in the VS Code terminal:
#   pip install pandas matplotlib seaborn

from retention_helpers import (
    calculate_revenue,
    clean_transactions,
    cohort_index,
)

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

# For your own data, set CSV_FILE to its path and map the column names below.
CSV_FILE = "Online Retail.csv"
CUSTOMER_COL = "CustomerID"
DATE_COL = "InvoiceDate"
ORDER_COL = "InvoiceNo"
PRICE_COL = "UnitPrice"
QUANTITY_COL = "Quantity"

sns.set_theme(style="whitegrid")


def make_sample_data():
    """Create a small example dataset so this script runs without a CSV."""
    rows = []
    dates = pd.date_range("2024-01-01", "2024-06-30", freq="D")
    customers = range(1001, 1121)

    for customer in customers:
        first_day = pd.Timestamp("2024-01-01") + pd.Timedelta(
            days=(customer % 150)
        )
        purchase_days = [first_day]

        # Some customers return for additional purchases.
        if customer % 3 != 0:
            purchase_days.append(first_day + pd.Timedelta(days=20 + customer % 45))
        if customer % 5 == 0:
            purchase_days.append(first_day + pd.Timedelta(days=65 + customer % 50))

        for order_num, day in enumerate(purchase_days, start=1):
            if day > dates[-1]:
                continue
            rows.append({
                CUSTOMER_COL: customer,
                ORDER_COL: f"{customer}-{order_num}",
                DATE_COL: day,
                QUANTITY_COL: 1 + customer % 4,
                PRICE_COL: 10 + customer % 90,
            })

    return pd.DataFrame(rows)


# Load data
if CSV_FILE and Path(CSV_FILE).exists():
    df = pd.read_csv(CSV_FILE)
else:
    print("No CSV found; running with generated sample data.")
    df = make_sample_data()

# Check required columns
required = [CUSTOMER_COL, DATE_COL, ORDER_COL, PRICE_COL, QUANTITY_COL]
missing = [column for column in required if column not in df.columns]
if missing:
    raise ValueError(
        f"Missing columns: {missing}. Update the column settings near the top."
    )

# Clean and prepare through the same helper exercised by the unit tests.
df = clean_transactions(
    df,
    CUSTOMER_COL,
    DATE_COL,
    ORDER_COL,
    PRICE_COL,
    QUANTITY_COL,
)

if df.empty:
    raise ValueError("No valid purchase rows remain after cleaning.")

df["Revenue"] = calculate_revenue(df[QUANTITY_COL], df[PRICE_COL])

# Aggregate invoice lines to orders
orders = (
    df.groupby([CUSTOMER_COL, ORDER_COL], as_index=False)
      .agg(OrderDate=(DATE_COL, "min"), Revenue=("Revenue", "sum"))
)

orders["OrderMonth"] = orders["OrderDate"].dt.to_period("M")
orders["CohortMonth"] = (
    orders.groupby(CUSTOMER_COL)["OrderDate"]
          .transform("min")
          .dt.to_period("M")
)
orders["CohortIndex"] = [
    cohort_index(order_month, cohort_month)
    for order_month, cohort_month in zip(
        orders["OrderMonth"], orders["CohortMonth"]
    )
]

# Summary metrics
customer_orders = orders.groupby(CUSTOMER_COL)[ORDER_COL].nunique()
repeat_rate = (customer_orders > 1).mean() * 100
total_customers = customer_orders.size
repeat_customers = int((customer_orders > 1).sum())
avg_order_value = orders["Revenue"].mean()

print("\n=== Ecommerce Retention Summary ===")
print(f"Valid orders:             {orders[ORDER_COL].nunique():,}")
print(f"Unique customers:         {total_customers:,}")
print(f"Repeat customers:         {repeat_customers:,} ({repeat_rate:.1f}%)")
print(f"Average order value:      {avg_order_value:,.2f}")
print(f"Total revenue:            {orders['Revenue'].sum():,.2f}")

# Monthly business trends
monthly = orders.groupby("OrderMonth").agg(
    Revenue=("Revenue", "sum"),
    Orders=(ORDER_COL, "nunique"),
    Customers=(CUSTOMER_COL, "nunique"),
)
monthly.index = monthly.index.astype(str)

# Cohort retention: active customers in month N / customers in cohort month 0
cohort_sizes = orders.groupby("CohortMonth")[CUSTOMER_COL].nunique()
active = orders.groupby(["CohortMonth", "CohortIndex"])[CUSTOMER_COL].nunique()
retention = active.unstack()
retention = retention.divide(cohort_sizes, axis=0) * 100
retention.index = retention.index.astype(str)
retention.columns.name = "Months Since First Purchase"

# Days from first to second order
orders_sorted = orders.sort_values([CUSTOMER_COL, "OrderDate"])
orders_sorted["PreviousOrderDate"] = orders_sorted.groupby(CUSTOMER_COL)["OrderDate"].shift()
orders_sorted["DaysBetweenOrders"] = (
    orders_sorted["OrderDate"] - orders_sorted["PreviousOrderDate"]
).dt.days
second_order_days = orders_sorted.loc[
    orders_sorted["DaysBetweenOrders"].notna(), "DaysBetweenOrders"
]

# Save tables
monthly.to_csv("monthly_summary.csv")
retention.to_csv("cohort_retention.csv")

# Charts
fig, axes = plt.subplots(1, 2, figsize=(14, 5))

monthly["Revenue"].plot(
    kind="line", marker="o", ax=axes[0], color="#2878B5"
)
axes[0].set_title("Monthly Revenue")
axes[0].set_xlabel("Month")
axes[0].set_ylabel("Revenue")
axes[0].tick_params(axis="x", rotation=45)

if not second_order_days.empty:
    sns.histplot(second_order_days, bins=20, ax=axes[1], color="#F28E2B")
    median_days = second_order_days.median()
    axes[1].axvline(
        median_days,
        color="red",
        linestyle="--",
        label=f"Median: {median_days:.0f} days",
    )
    axes[1].legend()
axes[1].set_title("Days Between Customer Orders")
axes[1].set_xlabel("Days")
axes[1].set_ylabel("Customers")

fig.tight_layout()
fig.savefig("retention_analysis.png", dpi=200, bbox_inches="tight")
plt.show()

# Save the order-gap view separately so the dashboard can place each chart in
# its own section instead of showing the combined analysis image twice.
fig_days, ax_days = plt.subplots(figsize=(8, 4.5))
if not second_order_days.empty:
    sns.histplot(second_order_days, bins=20, ax=ax_days, color="#F28E2B")
    median_days = second_order_days.median()
    ax_days.axvline(
        median_days,
        color="red",
        linestyle="--",
        label=f"Median: {median_days:.0f} days",
    )
    ax_days.legend()
else:
    ax_days.text(0.5, 0.5, "No consecutive customer orders", ha="center", va="center")
ax_days.set_title("Days Between Customer Orders")
ax_days.set_xlabel("Days")
ax_days.set_ylabel("Customers")
fig_days.tight_layout()
fig_days.savefig("days_between_orders.png", dpi=200, bbox_inches="tight")
plt.show()

# Cohort heatmap in its own larger figure
fig, ax = plt.subplots(figsize=(14, 8))
sns.heatmap(
    retention,
    mask=retention.isna(),
    annot=False,
    cmap="Blues",
    vmin=0,
    vmax=100,
    linewidths=0.4,
    linecolor="white",
    cbar_kws={"label": "Returning customers (%)"},
    ax=ax,
)
ax.set_title("Monthly Customer Cohort Retention", fontsize=16, pad=14)
ax.set_xlabel("Months Since First Purchase")
ax.set_ylabel("First Purchase Month")
ax.tick_params(axis="x", rotation=0)
ax.tick_params(axis="y", rotation=0)

fig.tight_layout()
fig.savefig("cohort_retention_heatmap.png", dpi=200, bbox_inches="tight")
plt.show()

print(
    "\nSaved: monthly_summary.csv, cohort_retention.csv, "
    "retention_analysis.png, days_between_orders.png, cohort_retention_heatmap.png"
)
