"""Local dashboard for the existing retention analysis outputs."""

from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st


ROOT = Path(__file__).resolve().parent
MONTHLY_FILE = ROOT / "monthly_summary.csv"
COHORT_FILE = ROOT / "cohort_retention.csv"

st.set_page_config(page_title="Customer Retention", page_icon="↗", layout="wide")
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&display=swap');
html, body, [class*="css"] { font-family: 'DM Sans', sans-serif; }
.stApp { background: #f5f8fc; }
[data-testid="stMetric"] { background: white; border: 1px solid #e4ebf4; padding: 18px 20px; border-radius: 14px; box-shadow: 0 3px 12px #183b6410; }
[data-testid="stMetricLabel"] { color: #52657c; }
.block-container { max-width: 1280px; padding-top: 2.2rem; }
</style>
""", unsafe_allow_html=True)

st.title("Customer retention & cohort analysis")
st.write("A clear view of customer repeat behavior, revenue trends, and how cohorts return over time.")

if not MONTHLY_FILE.exists() or not COHORT_FILE.exists():
    st.error("Analysis output files are missing. Run `python retention_analysis.py` from this folder to regenerate them.")
    st.stop()

monthly = pd.read_csv(MONTHLY_FILE)
cohorts = pd.read_csv(COHORT_FILE)

def find_column(frame, *names):
    lookup = {str(col).strip().lower().replace(" ", "_"): col for col in frame.columns}
    return next((lookup[name] for name in names if name in lookup), None)

revenue_col = find_column(monthly, "revenue", "total_revenue", "monthly_revenue")
month_col = find_column(monthly, "month", "order_month", "purchase_month", "year_month")
order_col = find_column(monthly, "orders", "order_count", "valid_orders", "total_orders")
customer_col = find_column(monthly, "customers", "unique_customers", "customer_count")

# Reconstruct order-level measures from the source analysis when available.
source = None
for candidate in (ROOT / "orders.csv", ROOT / "online_retail.csv", ROOT / "data.csv"):
    if candidate.exists():
        source = pd.read_csv(candidate)
        break
if source is None:
    for candidate in ROOT.glob("*.csv"):
        if candidate.name not in {MONTHLY_FILE.name, COHORT_FILE.name}:
            try:
                frame = pd.read_csv(candidate)
                if find_column(frame, "customer_id", "customerid", "customer") and find_column(frame, "invoice", "invoice_no", "order_id"):
                    source = frame
                    break
            except Exception:
                pass

order_count = customer_count = repeat_count = repeat_rate = aov = total_revenue = median_days = None
if source is not None:
    cust = find_column(source, "customer_id", "customerid", "customer")
    order = find_column(source, "invoice", "invoice_no", "order_id")
    amount = find_column(source, "amount", "revenue", "total", "sales", "line_total")
    date = find_column(source, "date", "order_date", "invoicedate", "invoice_date")
    valid = source.copy()
    if amount:
        valid[amount] = pd.to_numeric(valid[amount], errors="coerce")
        valid = valid[valid[amount] > 0]
        total_revenue = float(valid[amount].sum())
    if cust and order:
        valid = valid.dropna(subset=[cust, order])
        order_count = int(valid[order].nunique())
        by_customer = valid.groupby(cust)[order].nunique()
        customer_count = int(by_customer.size)
        repeat_count = int((by_customer > 1).sum())
        repeat_rate = repeat_count / customer_count if customer_count else 0
        if total_revenue is not None:
            aov = total_revenue / order_count if order_count else 0
        if date:
            dated = valid[[cust, order, date]].copy()
            dated[date] = pd.to_datetime(dated[date], errors="coerce")
            first_per_order = dated.dropna().sort_values(date).drop_duplicates([cust, order])
            gaps = first_per_order.groupby(cust)[date].diff().dt.days.dropna()
            if not gaps.empty:
                median_days = float(gaps.median())

if total_revenue is None and revenue_col:
    total_revenue = pd.to_numeric(monthly[revenue_col], errors="coerce").sum()
if customer_count is None and customer_col:
    customer_count = pd.to_numeric(monthly[customer_col], errors="coerce").sum()
if order_count is None and order_col:
    order_count = pd.to_numeric(monthly[order_col], errors="coerce").sum()
if aov is None and total_revenue is not None and order_count:
    aov = total_revenue / order_count

def show(value, kind="number"):
    if value is None or pd.isna(value):
        return "—"
    if kind == "money": return f"${value:,.2f}"
    if kind == "rate": return f"{value:.1%}"
    if kind == "days": return f"{value:,.0f} days"
    return f"{value:,.0f}"

cards = st.columns(4)
items = [("Valid orders", order_count, "number"), ("Unique customers", customer_count, "number"), ("Repeat customers", repeat_count, "number"), ("Repeat rate", repeat_rate, "rate")]
for col, (label, val, kind) in zip(cards, items): col.metric(label, show(val, kind))
cards = st.columns(3)
for col, (label, val, kind) in zip(cards, [("Average order value", aov, "money"), ("Total revenue", total_revenue, "money"), ("Median days between orders", median_days, "days")]): col.metric(label, show(val, kind))

st.markdown("## Trends and cohorts")
left, right = st.columns([1, 1])
with left:
    st.subheader("Monthly revenue")
    if month_col and revenue_col:
        chart_data = monthly[[month_col, revenue_col]].copy()
        chart_data[revenue_col] = pd.to_numeric(chart_data[revenue_col], errors="coerce")
        fig = px.line(chart_data, x=month_col, y=revenue_col, markers=True, labels={month_col: "Month", revenue_col: "Revenue"})
        fig.update_traces(line_color="#2878d0", fill="tozeroy", fillcolor="rgba(40,120,208,.10)")
        fig.update_layout(margin=dict(l=10,r=10,t=20,b=10), plot_bgcolor="white", paper_bgcolor="white", hovermode="x unified")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Monthly CSV needs a month and revenue column to draw this chart.")
with right:
    st.subheader("Cohort retention")
    # The analysis commonly exports a tidy table with cohort, period, and retention columns.
    cohort_col = find_column(cohorts, "cohort", "cohort_month", "first_purchase_month")
    period_col = find_column(cohorts, "period", "month_number", "months_since_first_purchase", "month_index")
    retention_col = find_column(cohorts, "retention", "retention_rate", "retention_pct", "customers_retained")
    if cohort_col and period_col and retention_col:
        values = pd.to_numeric(cohorts[retention_col], errors="coerce")
        # Convert percentage-point exports to a 0–1 scale for a consistent axis.
        if values.max() > 1.5: values = values / 100
        chart = cohorts.assign(_retention=values)
        fig = px.density_heatmap(chart, x=period_col, y=cohort_col, z="_retention", histfunc="avg", color_continuous_scale="Blues", labels={period_col:"Months since first purchase", cohort_col:"First-purchase month", "_retention":"Retention"})
        fig.update_layout(margin=dict(l=10,r=10,t=20,b=10), coloraxis_colorbar=dict(tickformat=".0%"), plot_bgcolor="white", paper_bgcolor="white")
        fig.update_coloraxes(colorbar_tickformat=".0%")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Cohort CSV format is not recognized for an interactive heatmap. See the existing cohort_retention_heatmap.png for the exported view.")
        image = ROOT / "cohort_retention_heatmap.png"
        if image.exists(): st.image(str(image), use_container_width=True)

st.caption("Rows are first-purchase months; columns are months since first purchase. Month 0 is 100%. Blank cells mean the dataset has no later-period data for that cohort.")

st.subheader("Days between orders")
if median_days is not None and source is not None:
    cust = find_column(source, "customer_id", "customerid", "customer")
    order = find_column(source, "invoice", "invoice_no", "order_id")
    date = find_column(source, "date", "order_date", "invoicedate", "invoice_date")
    dated = source[[cust, order, date]].copy()
    dated[date] = pd.to_datetime(dated[date], errors="coerce")
    dated = dated.dropna().sort_values(date).drop_duplicates([cust, order])
    gaps = dated.groupby(cust)[date].diff().dt.days.dropna()
    fig = px.histogram(x=gaps, nbins=24, labels={"x":"Days between orders", "count":"Customer intervals"}, color_discrete_sequence=["#2878d0"])
    fig.update_layout(margin=dict(l=10,r=10,t=20,b=10), plot_bgcolor="white", paper_bgcolor="white")
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("The supplied summaries do not include individual order dates, so the days-between-orders distribution cannot be reconstructed. The median is shown when source orders are available.")
    image = ROOT / "retention_analysis.png"
    if image.exists(): st.image(str(image), caption="Existing retention analysis output", use_container_width=True)

with st.expander("About the data"):
    st.write("This dashboard reads the generated monthly and cohort CSV files in this project folder. Customer and order metrics are calculated from source order records when they are available; otherwise, only metrics represented in the summary files can be shown.")
with st.expander("Limitations"):
    st.write("This analysis describes observed behavior in the available data. It does not prove why customers return, establish causation, or predict future retention. Incomplete observation windows leave later cohort periods blank.")

st.caption("To refresh the outputs, run `python retention_analysis.py` in the project folder, then refresh this page.")
