"""Playwright end-to-end checks for the local Retention Studio dashboard."""

import threading
import unittest
import csv
from decimal import Decimal
from http.server import ThreadingHTTPServer
from pathlib import Path

from playwright.sync_api import sync_playwright

from dashboard_server import DashboardHandler


class QuietDashboardHandler(DashboardHandler):
    """Keep HTTP access logs from interleaving with unittest's verbose results."""

    def log_message(self, format_string, *args):
        pass


class RetentionDashboardBrowserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), QuietDashboardHandler)
        cls.server_thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.server_thread.start()
        cls.base_url = f"http://127.0.0.1:{cls.server.server_address[1]}"
        cls.playwright = sync_playwright().start()
        cls.browser = cls.playwright.chromium.launch(headless=True)

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.playwright.stop()
        cls.server.shutdown()
        cls.server.server_close()
        cls.server_thread.join(timeout=5)

    def setUp(self):
        self.context = self.browser.new_context(viewport={"width": 1440, "height": 1000})
        self.page = self.context.new_page()
        source_fixture = (
            "CustomerID,InvoiceNo,InvoiceDate,Quantity,UnitPrice\n"
            "1,1001,2024-01-01,1,10\n"
            "1,1002,2024-02-01,1,25\n"
            "2,1003,2024-01-05,1,20\n"
        )
        self.page.route("**/*Retail.csv", lambda route: route.fulfill(body=source_fixture))
        self.page.goto(self.base_url, wait_until="domcontentloaded")
        self.page.wait_for_function(
            "document.querySelector('#revenueChart')?._points?.length > 0"
        )

    def tearDown(self):
        self.context.close()

    def test_dashboard_loads_project_heading_and_ready_status(self):
        self.assertIn("Retention, made", self.page.locator("h1").inner_text())
        self.assertTrue(self.page.locator("#status").inner_text().strip())

    def test_monthly_revenue_chart_reads_generated_csv(self):
        canvas = self.page.locator("#revenueChart")
        self.assertGreater(canvas.evaluate("node => node._points.length"), 0)
        self.assertEqual(self.page.locator("#revenue-empty").inner_text(), "")
        blue_pixels = canvas.evaluate("""node => {
          const ctx = node.getContext('2d');
          const pixels = ctx.getImageData(0, 0, node.width, node.height).data;
          let count = 0;
          for (let i = 0; i < pixels.length; i += 4) {
            if (pixels[i + 3] > 0 && pixels[i + 2] > pixels[i] + 20) count++;
          }
          return count;
        }""")
        self.assertGreater(blue_pixels, 20, "Revenue points must be visibly drawn in the monthly revenue panel.")

    def test_source_data_populates_repeat_customer_metrics(self):
        self.page.wait_for_function("document.querySelector('#repeat').textContent !== '—'")
        self.assertEqual(self.page.locator("#orders").inner_text(), "3")
        self.assertEqual(self.page.locator("#customers").inner_text(), "2")
        self.assertEqual(self.page.locator("#repeat").inner_text(), "1")
        self.assertEqual(self.page.locator("#rate").inner_text(), "50.0%")
        self.assertEqual(self.page.locator("#revenue").inner_text(), "$55.00")
        self.assertEqual(self.page.locator("#days").inner_text(), "31 days")

    def test_actual_project_csv_matches_monthly_order_summary(self):
        self.page.unroute("**/*Retail.csv")
        self.page.reload(wait_until="domcontentloaded")
        self.page.wait_for_function(
            "document.querySelector('#repeat').textContent !== '—'",
            timeout=120_000,
        )
        with (Path(__file__).resolve().parent / "monthly_summary.csv").open(
            newline="", encoding="utf-8"
        ) as summary_file:
            monthly_rows = list(csv.DictReader(summary_file))
        expected_orders = sum(int(row["Orders"]) for row in monthly_rows)
        expected_revenue = sum(Decimal(row["Revenue"]) for row in monthly_rows)
        self.assertEqual(self.page.locator("#orders").inner_text(), f"{expected_orders:,}")
        self.assertEqual(self.page.locator("#revenue").inner_text(), f"${expected_revenue:,.2f}")
        self.assertNotEqual(self.page.locator("#customers").inner_text(), "—")
        self.assertNotEqual(self.page.locator("#repeat").inner_text(), "—")
        self.assertNotEqual(self.page.locator("#days").inner_text(), "—")
        gap_chart = self.page.locator("#gap-image img")
        gap_chart.wait_for()
        self.assertIn("days_between_orders.png", gap_chart.get_attribute("src"))
        image_width = gap_chart.evaluate("img => img.naturalWidth")
        self.assertGreater(image_width, 0)

    def test_cohort_heatmap_shows_cohorts_and_month_zero(self):
        self.assertGreater(self.page.locator("#heatmap table.heatmap tbody tr").count(), 0)
        self.assertEqual(self.page.locator("#heatmap thead").get_by_text("Month 0").count(), 1)
        self.assertEqual(self.page.locator("#heatmap tbody tr:first-child th").inner_text(), "2010-01")

    def test_refresh_button_reloads_analysis_data(self):
        self.page.get_by_role("button", name="Refresh data").click()
        self.page.wait_for_function(
            "document.querySelector('#revenueChart')?._points?.length > 0"
        )
        self.assertGreater(self.page.locator("#revenueChart").evaluate("canvas => canvas._points.length"), 0)

    def test_missing_monthly_csv_shows_a_clear_error(self):
        self.page.route(
            "**/monthly_summary.csv",
            lambda route: route.fulfill(status=404, body="missing"),
        )
        self.page.reload(wait_until="domcontentloaded")
        self.page.get_by_text("monthly_summary.csv could not be loaded", exact=False).wait_for()
        self.assertIn("README_DASHBOARD.md", self.page.locator("#status").inner_text())

    def test_run_tests_button_reports_each_python_test_case(self):
        self.page.get_by_role("button", name="Run Python tests").click()
        self.page.get_by_text("35 passed · 0 failed · 0 skipped", exact=True).wait_for(timeout=120_000)
        self.assertEqual(self.page.locator("#test-results .test-row").count(), 35)

    def metric_value(self, label):
        card = self.page.locator(".metric").filter(has_text=label)
        return card.locator(".metric-value").inner_text()

    def replace_source_fixture(self, content):
        self.page.unroute("**/*Retail.csv")
        self.page.route("**/*Retail.csv", lambda route: route.fulfill(body=content))
        self.page.reload(wait_until="domcontentloaded")
        self.page.wait_for_function("document.querySelector('#revenueChart')?._points?.length > 0")

    def test_document_title_identifies_retention_studio(self):
        self.assertEqual(self.page.title(), "Retention Studio · Customer Analytics")

    def test_sidebar_has_overview_trends_testing_and_about_links(self):
        links = self.page.locator(".sidebar .side-link").all_inner_texts()
        self.assertEqual(len(links), 4)
        self.assertTrue(any("Testing" in link for link in links))
        self.assertTrue(any("Trends" in link for link in links))

    def test_about_data_section_explains_the_source_files(self):
        self.assertIn("monthly_summary.csv", self.page.locator("#about").inner_text())
        self.assertIn("cohort_retention.csv", self.page.locator("#about").inner_text())

    def test_limitations_section_discloses_observed_behavior_only(self):
        self.assertIn("does not prove why customers return", self.page.locator("#about").inner_text())

    def test_valid_orders_kpi_shows_three_fixture_orders(self):
        self.assertEqual(self.metric_value("Valid orders"), "3")

    def test_unique_customers_kpi_shows_two_fixture_customers(self):
        self.assertEqual(self.metric_value("Unique customers"), "2")

    def test_repeat_customers_kpi_shows_one_returning_customer(self):
        self.assertEqual(self.metric_value("Repeat customers"), "1")

    def test_repeat_rate_kpi_shows_fifty_percent(self):
        self.assertEqual(self.metric_value("Repeat rate"), "50.0%")

    def test_average_order_value_kpi_uses_fixture_revenue(self):
        self.assertEqual(self.metric_value("Average order value"), "$18.33")

    def test_total_revenue_kpi_shows_fixture_revenue(self):
        self.assertEqual(self.metric_value("Total revenue"), "$55.00")

    def test_median_order_interval_kpi_shows_thirty_one_days(self):
        self.assertEqual(self.metric_value("Median days between orders"), "31 days")

    def test_revenue_canvas_is_visible_and_has_a_drawn_size(self):
        canvas = self.page.locator("#revenueChart")
        self.assertTrue(canvas.is_visible())
        dimensions = canvas.evaluate("node => ({width: node.clientWidth, height: node.clientHeight})")
        self.assertGreater(dimensions["width"], 250)
        self.assertGreater(dimensions["height"], 150)

    def test_revenue_chart_has_a_point_for_each_summary_month(self):
        points = self.page.locator("#revenueChart").evaluate("canvas => canvas._points")
        with (Path(__file__).parent / "monthly_summary.csv").open(encoding="utf-8", newline="") as summary_file:
            month_count = sum(1 for _ in csv.DictReader(summary_file))
        self.assertEqual(len(points), month_count)
        self.assertTrue(all(point["label"] and point["value"] > 0 for point in points))

    def test_revenue_chart_hover_exposes_month_and_value(self):
        canvas = self.page.locator("#revenueChart")
        canvas.hover(position={"x": 55, "y": 80})
        tooltip = canvas.get_attribute("title")
        self.assertIn(": $", tooltip)

    def test_refresh_button_fetches_monthly_summary_again(self):
        requests = []
        self.page.on("request", lambda request: requests.append(request.url) if request.url.endswith("monthly_summary.csv") else None)
        before = len(requests)
        self.page.get_by_role("button", name="Refresh data").click()
        self.page.wait_for_function("document.querySelector('#revenueChart')?._points?.length > 0")
        self.assertGreater(len(requests), before)

    def test_cohort_first_period_is_one_hundred_percent(self):
        first_row = self.page.locator("#heatmap tbody tr:first-child")
        self.assertEqual(first_row.locator("th").inner_text(), "2010-01")
        self.assertEqual(first_row.locator("td").first.inner_text(), "100%")

    def test_cohort_heatmap_has_period_headers_zero_through_twenty_three(self):
        headers = self.page.locator("#heatmap thead th").all_inner_texts()
        self.assertEqual(len(headers) - 1, 24)
        self.assertEqual(headers[1], "Month 0")
        self.assertEqual(headers[-1], "Month 23")

    def test_unobserved_future_cohort_periods_are_blank(self):
        newest = self.page.locator("#heatmap tbody tr").last
        self.assertEqual(newest.locator("td").last.inner_text(), "")

    def test_dashboard_has_no_horizontal_overflow_on_mobile(self):
        self.page.set_viewport_size({"width": 390, "height": 844})
        dimensions = self.page.evaluate("({viewport: innerWidth, page: document.documentElement.scrollWidth})")
        self.assertLessEqual(dimensions["page"], dimensions["viewport"])

    def test_revenue_chart_remains_inside_its_card_on_mobile(self):
        self.page.set_viewport_size({"width": 390, "height": 844})
        dimensions = self.page.evaluate("""() => {
          const card = document.querySelector('.revenue-panel').getBoundingClientRect();
          const plot = document.querySelector('#revenueChart').getBoundingClientRect();
          return {cardRight: card.right, plotRight: plot.right, plotWidth: plot.width};
        }""")
        self.assertGreater(dimensions["plotWidth"], 250)
        self.assertLessEqual(dimensions["plotRight"], dimensions["cardRight"] + 1)

    def test_all_six_assessment_artifact_links_are_available(self):
        links = self.page.locator(".artifact-links a")
        self.assertEqual(links.count(), 6)
        self.assertEqual(set(links.all_inner_texts()), {"Test Plan", "Test Cases", "Bug Report", "RTM", "Test Summary", "Code Analysis"})

    def test_python_and_browser_test_controls_are_visible(self):
        self.assertTrue(self.page.get_by_role("button", name="Run Python tests").is_visible())
        self.assertTrue(self.page.get_by_role("button", name="Run browser tests").is_visible())

    def test_missing_source_csv_marks_customer_metrics_unavailable(self):
        self.page.unroute("**/*Retail.csv")
        for filename in ("Online%20Retail.csv", "orders.csv", "online_retail.csv", "data.csv", "retail.csv"):
            self.page.route(f"**/{filename}", lambda route: route.fulfill(status=404, body="missing"))
        self.page.reload(wait_until="domcontentloaded")
        self.page.get_by_text("Add the source order CSV", exact=False).wait_for()
        self.assertEqual(self.metric_value("Unique customers"), "—")
        self.assertEqual(self.metric_value("Repeat rate"), "—")

    def test_cancelled_invoice_lines_do_not_inflate_source_totals(self):
        data = (
            "CustomerID,InvoiceNo,InvoiceDate,Quantity,UnitPrice\n"
            "1,1001,2024-01-01,1,10\n"
            "1,c1002,2024-02-01,1,999\n"
            "2, C1003,2024-02-02,1,999\n"
            "2,1004,2024-03-01,1,20\n"
        )
        self.replace_source_fixture(data)
        self.assertEqual(self.metric_value("Valid orders"), "2")
        self.assertEqual(self.metric_value("Total revenue"), "$30.00")
        self.assertEqual(self.metric_value("Repeat customers"), "0")


    def test_zero_quantity_source_line_is_ignored(self):
        data = (
            "CustomerID,InvoiceNo,InvoiceDate,Quantity,UnitPrice\n"
            "1,1001,2024-01-01,1,10\n"
            "1,1002,2024-02-01,0,500\n"
        )
        self.replace_source_fixture(data)
        self.assertEqual(self.metric_value("Valid orders"), "1")
        self.assertEqual(self.metric_value("Total revenue"), "$10.00")

    def test_non_finite_price_source_line_is_ignored(self):
        data = (
            "CustomerID,InvoiceNo,InvoiceDate,Quantity,UnitPrice\n"
            "1,1001,2024-01-01,1,10\n"
            "1,1002,2024-02-01,1,Infinity\n"
        )
        self.replace_source_fixture(data)
        self.assertEqual(self.metric_value("Valid orders"), "1")
        self.assertEqual(self.metric_value("Total revenue"), "$10.00")

    def test_invalid_date_source_line_is_ignored(self):
        data = (
            "CustomerID,InvoiceNo,InvoiceDate,Quantity,UnitPrice\n"
            "1,1001,2024-01-01,1,10\n"
            "1,1002,not-a-date,1,500\n"
        )
        self.replace_source_fixture(data)
        self.assertEqual(self.metric_value("Valid orders"), "1")
        self.assertEqual(self.metric_value("Total revenue"), "$10.00")


if __name__ == "__main__":
    unittest.main(verbosity=2)
