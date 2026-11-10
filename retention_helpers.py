import math

import pandas as pd


def clean_transactions(df, customer_col, date_col, order_col, price_col, quantity_col):
    df = df.copy()

    df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
    df[price_col] = pd.to_numeric(df[price_col], errors="coerce")
    df[quantity_col] = pd.to_numeric(df[quantity_col], errors="coerce")

    df = df.dropna(
        subset=[customer_col, date_col, order_col, price_col, quantity_col]
    )
    # Invoice IDs may contain accidental surrounding spaces or lowercase c.
    cancelled = df[order_col].astype(str).str.strip().str.upper().str.startswith("C")
    df = df[~cancelled]

    # Positive infinity passes a simple > 0 check, but is not valid transaction data.
    finite_values = df[price_col].map(math.isfinite) & df[quantity_col].map(math.isfinite)
    df = df[finite_values & (df[quantity_col] > 0) & (df[price_col] > 0)]

    return df.copy()


def calculate_revenue(quantity, unit_price):
    return quantity * unit_price


def cohort_index(order_month, cohort_month):
    return order_month.ordinal - cohort_month.ordinal
