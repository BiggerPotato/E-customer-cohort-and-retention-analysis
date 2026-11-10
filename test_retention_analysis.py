import os
import subprocess
import sys
import unittest
from pathlib import Path

import pandas as pd

from retention_helpers import (
    calculate_revenue,
    clean_transactions,
    cohort_index,
)

CUSTOMER = "CustomerID"
DATE = "InvoiceDate"
ORDER = "InvoiceNo"
PRICE = "UnitPrice"
QUANTITY = "Quantity"


def one_row(customer=1, date="2024-01-15", invoice="1001",
            price=10, quantity=1):
    return pd.DataFrame([{
        CUSTOMER: customer,
        DATE: date,
        ORDER: invoice,
        PRICE: price,
        QUANTITY: quantity,
    }])


def clean(data):
    return clean_transactions(
        data, CUSTOMER, DATE, ORDER, PRICE, QUANTITY
    )


class RevenueUnitTests(unittest.TestCase):
    # 1
    def test_revenue_integer_values(self):
        self.assertEqual(calculate_revenue(2, 10), 20)

    # 2
    def test_revenue_decimal_values(self):
        self.assertAlmostEqual(calculate_revenue(3, 0.5), 1.5)

    # 3
    def test_revenue_for_one_item(self):
        self.assertEqual(calculate_revenue(1, 25), 25)

    # 4
    def test_revenue_for_zero_quantity_is_zero(self):
        self.assertEqual(calculate_revenue(0, 10), 0)

    # 5
    def test_revenue_accepts_series(self):
        result = calculate_revenue(
            pd.Series([1, 2]), pd.Series([10, 5])
        )
        self.assertEqual(result.tolist(), [10, 10])


class CleaningWhiteBoxTests(unittest.TestCase):
    # 6: valid row
    def test_valid_purchase_is_kept(self):
        self.assertEqual(len(clean(one_row())), 1)

    # 7: lower boundary for quantity
    def test_zero_quantity_is_removed(self):
        self.assertEqual(len(clean(one_row(quantity=0))), 0)

    # 8: below quantity boundary
    def test_negative_quantity_is_removed(self):
        self.assertEqual(len(clean(one_row(quantity=-1))), 0)

    # 9: just above quantity boundary
    def test_positive_fractional_quantity_is_kept(self):
        self.assertEqual(len(clean(one_row(quantity=0.5))), 1)

    # 10: lower boundary for price
    def test_zero_price_is_removed(self):
        self.assertEqual(len(clean(one_row(price=0))), 0)

    # 11: below price boundary
    def test_negative_price_is_removed(self):
        self.assertEqual(len(clean(one_row(price=-0.01))), 0)

    # 12: just above price boundary
    def test_small_positive_price_is_kept(self):
        self.assertEqual(len(clean(one_row(price=0.01))), 1)

    # 13: cancelled invoice condition
    def test_cancelled_invoice_is_removed(self):
        self.assertEqual(len(clean(one_row(invoice="C1001"))), 0)

    # 14: ordinary invoice condition
    def test_normal_invoice_is_kept(self):
        self.assertEqual(len(clean(one_row(invoice="1001"))), 1)

    # 15
    def test_missing_customer_is_removed(self):
        data = one_row()
        data.loc[0, CUSTOMER] = None
        self.assertEqual(len(clean(data)), 0)

    # 16
    def test_missing_date_is_removed(self):
        data = one_row()
        data.loc[0, DATE] = None
        self.assertEqual(len(clean(data)), 0)

    # 17
    def test_missing_invoice_is_removed(self):
        data = one_row()
        data.loc[0, ORDER] = None
        self.assertEqual(len(clean(data)), 0)

    # 18
    def test_missing_price_is_removed(self):
        data = one_row()
        data.loc[0, PRICE] = None
        self.assertEqual(len(clean(data)), 0)

    # 19
    def test_missing_quantity_is_removed(self):
        data = one_row()
        data.loc[0, QUANTITY] = None
        self.assertEqual(len(clean(data)), 0)

    # 20
    def test_invalid_date_is_removed(self):
        self.assertEqual(len(clean(one_row(date="not-a-date"))), 0)

    # 21
    def test_numeric_text_is_converted_and_kept(self):
        data = one_row(price="10.5", quantity="2")
        result = clean(data)
        self.assertEqual(len(result), 1)
        self.assertEqual(result.iloc[0][PRICE], 10.5)
        self.assertEqual(result.iloc[0][QUANTITY], 2)

    # 31: lowercase cancellation prefix is rejected
    def test_lowercase_cancelled_invoice_is_removed(self):
        self.assertEqual(len(clean(one_row(invoice="c1001"))), 0)

    # 32: leading spaces do not bypass cancellation check
    def test_spaced_cancelled_invoice_is_removed(self):
        self.assertEqual(len(clean(one_row(invoice=" C1001"))), 0)

    # 33: infinite prices are rejected as invalid transaction data
    def test_infinite_price_is_removed(self):
        self.assertEqual(len(clean(one_row(price=float("inf")))), 0)


class CohortUnitTests(unittest.TestCase):
    # 22
    def test_same_month_index_is_zero(self):
        month = pd.Period("2024-01", freq="M")
        self.assertEqual(cohort_index(month, month), 0)

    # 23
    def test_next_month_index_is_one(self):
        self.assertEqual(
            cohort_index(pd.Period("2024-02", freq="M"),
                         pd.Period("2024-01", freq="M")),
            1,
        )

    # 24
    def test_six_month_index(self):
        self.assertEqual(
            cohort_index(pd.Period("2024-07", freq="M"),
                         pd.Period("2024-01", freq="M")),
            6,
        )

    # 25
    def test_cohort_index_across_year_boundary(self):
        self.assertEqual(
            cohort_index(pd.Period("2025-01", freq="M"),
                         pd.Period("2024-12", freq="M")),
            1,
        )


class IntegrationTests(unittest.TestCase):
    # 26
    def test_cleaning_then_revenue_calculation(self):
        data = one_row(price=10, quantity=2)
        result = clean(data)
        result["Revenue"] = calculate_revenue(
            result[QUANTITY], result[PRICE]
        )
        self.assertEqual(result.iloc[0]["Revenue"], 20)

    # 27
    def test_multiple_items_aggregate_to_one_order(self):
        data = pd.DataFrame([
            [1, "2024-01-15", "1001", 10, 2],
            [1, "2024-01-15", "1001", 5, 3],
        ], columns=[CUSTOMER, DATE, ORDER, PRICE, QUANTITY])
        result = clean(data)
        result["Revenue"] = calculate_revenue(
            result[QUANTITY], result[PRICE]
        )
        orders = result.groupby([CUSTOMER, ORDER])["Revenue"].sum()
        self.assertEqual(len(orders), 1)
        self.assertEqual(orders.iloc[0], 35)

    # 28
    def test_repeat_customer_count_from_two_orders(self):
        orders = pd.DataFrame([
            [1, "A"], [1, "B"], [2, "C"]
        ], columns=[CUSTOMER, ORDER])
        order_counts = orders.groupby(CUSTOMER)[ORDER].nunique()
        repeat_count = int((order_counts > 1).sum())
        self.assertEqual(repeat_count, 1)

    # 29
    def test_cohort_retention_example(self):
        # Two customers start in January; one returns in February.
        orders = pd.DataFrame([
            [1, pd.Period("2024-01", freq="M")],
            [2, pd.Period("2024-01", freq="M")],
            [1, pd.Period("2024-02", freq="M")],
        ], columns=[CUSTOMER, "OrderMonth"])

        orders["CohortMonth"] = orders.groupby(CUSTOMER)[
            "OrderMonth"
        ].transform("min")
        orders["CohortIndex"] = [
            cohort_index(order_month, cohort_month)
            for order_month, cohort_month in zip(
                orders["OrderMonth"], orders["CohortMonth"]
            )
        ]

        active = orders.groupby("CohortIndex")[CUSTOMER].nunique()
        self.assertEqual(active.loc[0], 2)
        self.assertEqual(active.loc[1], 1)
        self.assertAlmostEqual(active.loc[1] / active.loc[0], 0.5)

        # 34 — should pass
    def test_empty_input_stays_empty(self):
        data = pd.DataFrame(
            columns=[CUSTOMER, DATE, ORDER, PRICE, QUANTITY]
        )
        self.assertTrue(clean(data).empty)

    # 35 — should pass
    def test_two_valid_customers_are_preserved(self):
        data = pd.DataFrame([
            [1, "2024-01-15", "1001", 10, 1],
            [2, "2024-01-16", "1002", 20, 1],
        ], columns=[CUSTOMER, DATE, ORDER, PRICE, QUANTITY])

        self.assertEqual(len(clean(data)), 2)

class BlackBoxSystemTest(unittest.TestCase):
    # 30
    def test_full_program_runs_and_creates_outputs(self):
        folder = Path(__file__).resolve().parent
        script = folder / "retention_analysis.py"

        env = os.environ.copy()
        env["MPLBACKEND"] = "Agg"

        result = subprocess.run(
            [sys.executable, str(script)],
            cwd=folder,
            env=env,
            capture_output=True,
            text=True,
            timeout=180,
        )

        self.assertEqual(
            result.returncode, 0,
            msg=f"Program failed:\n{result.stderr}",
        )
        self.assertIn("Ecommerce Retention Summary", result.stdout)

        for filename in [
            "monthly_summary.csv",
            "cohort_retention.csv",
            "retention_analysis.png",
            "days_between_orders.png",
            "cohort_retention_heatmap.png",
        ]:
            self.assertTrue(
                (folder / filename).exists(),
                msg=f"Missing output file: {filename}",
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
