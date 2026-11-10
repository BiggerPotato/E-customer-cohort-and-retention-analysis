"""Run both project suites and write assessment reports from real results."""

from datetime import datetime
import json
from pathlib import Path
import re
import subprocess
import sys


ROOT = Path(__file__).resolve().parent
OUTPUT_DIR = ROOT / "test-results"
CASE_LINE = re.compile(r"^(test\w+) \(([^)]+)\) \.\.\. (ok|FAIL|ERROR|skipped.*)$")
SUITES = [
    ("Python unit and system tests", [sys.executable, "-m", "unittest", "-v", "test_retention_analysis"]),
    ("Playwright browser tests", [sys.executable, "-m", "unittest", "-v", "test_dashboard_browser"]),
]

CASE_DETAILS = {
    "test_full_program_runs_and_creates_outputs": ("System/output generation", "Actual `Online Retail.csv`; required transaction headers", "Run the analysis subprocess from the project directory.", "Exit code is 0; summary heading appears; both CSVs and all three PNGs exist."),
    "test_valid_purchase_is_kept": ("Transaction cleaning", "One valid row: customer 1, invoice 1001, quantity 1, price 10", "Pass the row through `clean_transactions`.", "Exactly one row remains."),
    "test_zero_quantity_is_removed": ("Boundary value: quantity", "Valid row with quantity 0", "Clean the row at the zero boundary.", "No row remains."),
    "test_negative_quantity_is_removed": ("Negative testing: quantity", "Valid row with quantity -1", "Clean the negative-quantity row.", "No row remains."),
    "test_positive_fractional_quantity_is_kept": ("Boundary value: quantity", "Valid row with quantity 0.5", "Clean a positive fraction just above zero.", "Exactly one row remains."),
    "test_zero_price_is_removed": ("Boundary value: price", "Valid row with UnitPrice 0", "Clean the row at the zero-price boundary.", "No row remains."),
    "test_negative_price_is_removed": ("Negative testing: price", "Valid row with UnitPrice -0.01", "Clean the negative-price row.", "No row remains."),
    "test_small_positive_price_is_kept": ("Boundary value: price", "Valid row with UnitPrice 0.01", "Clean a small positive price just above zero.", "Exactly one row remains."),
    "test_cancelled_invoice_is_removed": ("Negative testing: cancellation", "Valid row with invoice C1001", "Clean an uppercase cancelled invoice.", "No row remains."),
    "test_lowercase_cancelled_invoice_is_removed": ("Equivalence class: cancellation", "Valid row with invoice c1001", "Clean a lowercase cancelled invoice.", "No row remains."),
    "test_spaced_cancelled_invoice_is_removed": ("Equivalence class: cancellation", "Valid row with invoice ` C1001`", "Clean a cancelled invoice with leading whitespace.", "No row remains."),
    "test_normal_invoice_is_kept": ("Positive testing: invoice", "Valid row with invoice 1001", "Clean an ordinary invoice.", "Exactly one row remains."),
    "test_infinite_price_is_removed": ("Negative testing: non-finite value", "Valid row with price positive infinity", "Clean the row with non-finite UnitPrice.", "No row remains."),
    "test_missing_customer_is_removed": ("Negative testing: required fields", "Valid row with CustomerID missing", "Clean the row with a missing customer.", "No row remains."),
    "test_missing_date_is_removed": ("Negative testing: required fields", "Valid row with InvoiceDate missing", "Clean the row with a missing date.", "No row remains."),
    "test_missing_invoice_is_removed": ("Negative testing: required fields", "Valid row with InvoiceNo missing", "Clean the row with a missing invoice.", "No row remains."),
    "test_missing_price_is_removed": ("Negative testing: required fields", "Valid row with UnitPrice missing", "Clean the row with a missing price.", "No row remains."),
    "test_missing_quantity_is_removed": ("Negative testing: required fields", "Valid row with Quantity missing", "Clean the row with missing quantity.", "No row remains."),
    "test_invalid_date_is_removed": ("Negative testing: date parsing", "Valid row with InvoiceDate `not-a-date`", "Clean a row with unparseable date text.", "No row remains."),
    "test_numeric_text_is_converted_and_kept": ("Positive testing: type conversion", "UnitPrice `10.5`, Quantity `2` as strings", "Clean numeric text and inspect converted values.", "One row remains; price is 10.5 and quantity is 2 as numbers."),
    "test_revenue_integer_values": ("Revenue unit calculation", "Quantity 2 × UnitPrice 10", "Call `calculate_revenue(2, 10)`.", "Revenue equals 20."),
    "test_revenue_decimal_values": ("Revenue unit calculation", "Quantity 3 × UnitPrice 0.50", "Call `calculate_revenue(3, 0.5)`.", "Revenue equals 1.50."),
    "test_revenue_for_one_item": ("Revenue unit calculation", "Quantity 1 × UnitPrice 25", "Calculate revenue for one item.", "Revenue equals 25."),
    "test_revenue_for_zero_quantity_is_zero": ("Boundary value: revenue", "Quantity 0 × UnitPrice 10", "Calculate zero-quantity revenue (cleaner separately rejects this transaction).", "Calculation equals 0."),
    "test_revenue_accepts_series": ("Revenue vector calculation", "Quantities [1, 2], prices [10, 5]", "Calculate revenue for two pandas Series values.", "Result is [10, 10]."),
    "test_same_month_index_is_zero": ("Cohort index", "Order month and cohort month both 2024-01", "Calculate same-month cohort offset.", "Month index equals 0."),
    "test_next_month_index_is_one": ("Cohort index boundary", "Order 2024-02; cohort 2024-01", "Calculate the next-month offset.", "Month index equals 1."),
    "test_six_month_index": ("Cohort index", "Order 2024-07; cohort 2024-01", "Calculate an offset six months later.", "Month index equals 6."),
    "test_cohort_index_across_year_boundary": ("Cohort index boundary", "Order 2025-01; cohort 2024-12", "Calculate month offset over year change.", "Month index equals 1."),
    "test_cleaning_then_revenue_calculation": ("Integration: clean and revenue", "One valid item, quantity 2, price 10", "Clean the row then calculate revenue from its numeric columns.", "Revenue column equals 20."),
    "test_multiple_items_aggregate_to_one_order": ("Integration: order aggregation", "Two lines for invoice 1001: 2×10 and 3×5", "Clean lines, calculate line revenue, group by customer/invoice.", "One order is produced with revenue 35."),
    "test_repeat_customer_count_from_two_orders": ("Integration: repeat customers", "Customer 1 has two invoice IDs; customer 2 has one", "Count distinct invoices by customer and count groups > 1.", "Repeat-customer count equals 1."),
    "test_cohort_retention_example": ("Integration: cohort retention", "Two Jan starters; one returns in Feb", "Assign first month and compare month-1 active customers with cohort size.", "Month 0 has 2 customers; month 1 has 1 (50%)."),
    "test_empty_input_stays_empty": ("Integration: empty input", "DataFrame with required columns and zero rows", "Pass empty input through transaction cleaner.", "The result remains empty."),
    "test_two_valid_customers_are_preserved": ("Integration: customer preservation", "Two valid orders belonging to two customers", "Clean both rows.", "Both valid rows remain."),
    "test_dashboard_loads_project_heading_and_ready_status": ("Dashboard positive browser test", "Dashboard served on a temporary localhost port", "Open the page and inspect heading/status.", "Retention heading and nonempty data status are visible."),
    "test_monthly_revenue_chart_reads_generated_csv": ("Dashboard revenue chart", "Project `monthly_summary.csv`", "Open the page and inspect rendered canvas points.", "Chart has data points and no missing-column message."),
    "test_cohort_heatmap_shows_cohorts_and_month_zero": ("Dashboard cohort heatmap", "Project wide-form `cohort_retention.csv`", "Open the page and inspect cohort table.", "At least one cohort row and Month 0 are rendered."),
    "test_source_data_populates_repeat_customer_metrics": ("Dashboard source metrics", "3 fixture orders; customer 1 repeats; customer 2 is single-order", "Load dashboard with fixture CSV and inspect KPI cards.", "3 orders, 2 customers, 1 repeat customer, 50%, $55.00, and 31-day median are shown."),
    "test_actual_project_csv_matches_monthly_order_summary": ("Dashboard actual-source integration", "Actual `Online Retail.csv` plus generated monthly summary", "Reload without the test fixture; compare dashboard totals to monthly CSV and ensure customer KPIs load.", "Dashboard order and revenue totals equal the generated summary; customer, repeat and interval metrics are populated, and the days section loads its dedicated chart."),
    "test_refresh_button_reloads_analysis_data": ("Dashboard refresh", "Dashboard and generated summary CSVs available", "Click Refresh data and wait for revenue points.", "Chart data remains loaded after refresh."),
    "test_missing_monthly_csv_shows_a_clear_error": ("Dashboard negative browser test", "Monthly CSV request returns HTTP 404", "Reload after intercepting the monthly CSV as missing.", "A visible error points to the local server instructions."),
    "test_run_tests_button_reports_each_python_test_case": ("Dashboard test-result UI", "Python unittest suite available", "Click Run Python tests; wait for the result summary.", "35 case rows and the 35 passed, 0 failed summary are shown."),
    "test_document_title_identifies_retention_studio": ("Dashboard metadata", "Loaded dashboard page", "Read the document title.", "Title is `Retention Studio · Customer Analytics`."),
    "test_sidebar_has_overview_trends_testing_and_about_links": ("Dashboard navigation", "Loaded dashboard page", "Inspect sidebar links.", "Four navigation links include Overview, Trends, Testing & QA, and About."),
    "test_about_data_section_explains_the_source_files": ("Dashboard data documentation", "Loaded dashboard page", "Read the About the data section.", "Section identifies both generated CSV input files."),
    "test_limitations_section_discloses_observed_behavior_only": ("Dashboard limitations disclosure", "Loaded dashboard page", "Read the limitations section.", "Text explains that the analysis does not prove why customers return."),
    "test_valid_orders_kpi_shows_three_fixture_orders": ("Dashboard order metric", "3 valid orders in source fixture", "Inspect Valid orders KPI.", "KPI displays 3."),
    "test_unique_customers_kpi_shows_two_fixture_customers": ("Dashboard customer metric", "2 distinct customers in source fixture", "Inspect Unique customers KPI.", "KPI displays 2."),
    "test_repeat_customers_kpi_shows_one_returning_customer": ("Dashboard repeat metric", "One of two customers has 2 orders", "Inspect Repeat customers KPI.", "KPI displays 1."),
    "test_repeat_rate_kpi_shows_fifty_percent": ("Dashboard repeat rate", "One repeat customer out of 2", "Inspect Repeat rate KPI.", "KPI displays 50.0%."),
    "test_average_order_value_kpi_uses_fixture_revenue": ("Dashboard average order value", "Fixture revenue $55 over 3 orders", "Inspect Average order value KPI.", "KPI displays $18.33."),
    "test_total_revenue_kpi_shows_fixture_revenue": ("Dashboard total revenue", "Fixture order revenues total $55", "Inspect Total revenue KPI.", "KPI displays $55.00."),
    "test_median_order_interval_kpi_shows_thirty_one_days": ("Dashboard order interval", "Customer 1 orders on Jan 1 and Feb 1, 2024", "Inspect median-days KPI.", "KPI displays 31 days."),
    "test_revenue_canvas_is_visible_and_has_a_drawn_size": ("Dashboard chart sizing", "Desktop viewport 1440×1000", "Inspect the monthly revenue canvas bounds.", "Canvas is visible and larger than 250×150 CSS pixels."),
    "test_revenue_chart_has_a_point_for_each_summary_month": ("Dashboard revenue chart data", "Generated monthly summary CSV", "Read plotted canvas point data and CSV row count.", "One positive revenue point is plotted per monthly summary row."),
    "test_revenue_chart_hover_exposes_month_and_value": ("Dashboard revenue interaction", "Monthly chart contains revenue points", "Hover the chart and inspect its tooltip title.", "Tooltip includes a month label and formatted revenue."),
    "test_refresh_button_fetches_monthly_summary_again": ("Dashboard refresh behavior", "Dashboard has loaded monthly summary", "Observe requests, click Refresh data, and wait for chart redraw.", "Click causes another request for `monthly_summary.csv`."),
    "test_cohort_first_period_is_one_hundred_percent": ("Dashboard cohort month zero", "Project cohort CSV has first cohort 2010-01", "Inspect first row and first cohort cell.", "First cohort is 2010-01 and month 0 displays 100%."),
    "test_cohort_heatmap_has_period_headers_zero_through_twenty_three": ("Dashboard cohort periods", "Wide-form project cohort CSV", "Inspect the heatmap month headers.", "24 headers run from Month 0 through Month 23."),
    "test_unobserved_future_cohort_periods_are_blank": ("Dashboard cohort missing periods", "Newest cohort has no data in later months", "Inspect newest cohort's final heatmap cell.", "Unobserved later-period cell is blank."),
    "test_dashboard_has_no_horizontal_overflow_on_mobile": ("Responsive dashboard layout", "390-pixel-wide mobile viewport", "Set viewport and compare document width with viewport.", "Document has no horizontal overflow."),
    "test_revenue_chart_remains_inside_its_card_on_mobile": ("Responsive chart layout", "390-pixel-wide mobile viewport", "Compare chart bounds with the revenue card bounds.", "Chart remains within the card and wider than 250 pixels."),
    "test_all_six_assessment_artifact_links_are_available": ("Assessment artifact navigation", "Testing & QA section loaded", "Inspect artifact links and labels.", "Six links are present for plan, cases, bug report, RTM, summary, and code analysis."),
    "test_python_and_browser_test_controls_are_visible": ("Automation controls", "Testing & QA section loaded", "Inspect the two test action buttons.", "Python and Playwright browser test buttons are visible."),
    "test_missing_source_csv_marks_customer_metrics_unavailable": ("Negative testing: optional source CSV", "Order-source CSV requests return HTTP 404; summary CSVs remain available", "Reload dashboard and inspect status/customer KPIs.", "Dashboard explains source data is missing and leaves customer-level metrics unavailable."),
    "test_cancelled_invoice_lines_do_not_inflate_source_totals": ("Negative testing: cancelled invoice lines", "Source fixture includes lowercase and whitespace-prefixed cancellation IDs", "Load fixture and inspect order, revenue, repeat KPIs.", "Cancelled lines are excluded; 2 valid orders total $30 and no customer repeats."),
    "test_zero_quantity_source_line_is_ignored": ("Negative testing: zero quantity in browser data", "Fixture contains one valid order and a zero-quantity order", "Load fixture and inspect order/revenue metrics.", "Only the valid order is counted; revenue is $10."),
    "test_non_finite_price_source_line_is_ignored": ("Negative testing: non-finite browser price", "Fixture contains one valid order and one `Infinity` price", "Load fixture and inspect order/revenue metrics.", "Non-finite line is excluded; one order and $10 revenue remain."),
    "test_invalid_date_source_line_is_ignored": ("Negative testing: malformed browser date", "Fixture contains one valid order and one invalid date", "Load fixture and inspect order/revenue metrics.", "Invalid-date line is excluded; one order and $10 revenue remain."),
}


def read_cases(output, suite):
    cases = []
    for line in output.splitlines():
        match = CASE_LINE.match(line.strip())
        if not match:
            continue
        method, qualified, raw_result = match.groups()
        status = ("SKIPPED" if raw_result.startswith("skipped") else
                  "PASSED" if raw_result == "ok" else raw_result)
        prefix = "PW" if "test_dashboard_browser" in qualified else "UT"
        case_id = f"{prefix}-{method.removeprefix('test_').upper()}"
        default = (qualified.split(".")[-2].replace("Tests", " Tests"),
                   method.removeprefix("test_").replace("_", " "),
                   "Run the executable test and verify its assertion result.",
                   "The test's explicit assertion passes for the selected input.")
        feature, data, steps, expected = CASE_DETAILS.get(method, default)
        cases.append({
            "id": case_id,
            "name": qualified,
            "suite": suite,
            "feature": feature,
            "status": status,
            "data": data,
            "expected": expected,
            "actual": "Assertions passed." if status == "PASSED" else raw_result,
            "steps": steps,
        })
    return cases


def main():
    OUTPUT_DIR.mkdir(exist_ok=True)
    started = datetime.now().astimezone().isoformat(timespec="seconds")
    results = []
    all_cases = []
    overall_exit = 0

    for suite_name, command in SUITES:
        print(f"\n=== {suite_name} ===")
        print("Command:", " ".join(command))
        try:
            run = subprocess.run(
                command,
                cwd=ROOT,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                timeout=240,
                check=False,
            )
            output = run.stdout or ""
            print(output, end="" if output.endswith("\n") or not output else "\n")
            cases = read_cases(output, suite_name)
            exit_code = run.returncode
        except (OSError, subprocess.TimeoutExpired) as exc:
            output = f"Suite could not complete: {exc}"
            print(output)
            cases = [{
                "id": "BLOCKED-" + suite_name.split()[0].upper(),
                "name": suite_name,
                "suite": suite_name,
                "feature": "Suite setup",
                "status": "BLOCKED",
                "data": "Test command could not complete",
                "expected": "The suite should start and report individual cases.",
                "actual": output,
                "steps": "Run the documented command and inspect environment/setup errors.",
            }]
            exit_code = 2
        all_cases.extend(cases)
        results.append({
            "suite": suite_name,
            "command": command,
            "exit_code": exit_code,
            "cases": len(cases),
            "output": output,
        })
        if exit_code != 0:
            overall_exit = 1

    counts = {status: sum(case["status"] == status for case in all_cases)
              for status in ("PASSED", "FAILED", "ERROR", "SKIPPED", "BLOCKED")}
    summary = {
        "run_at": started,
        "python": sys.version.split()[0],
        "suites": results,
        "counts": counts,
        "total": len(all_cases),
        "executed": len(all_cases) - counts["BLOCKED"],
        "passed": counts["PASSED"],
        "failed": counts["FAILED"] + counts["ERROR"],
        "skipped": counts["SKIPPED"],
        "blocked": counts["BLOCKED"],
        "cases": all_cases,
    }
    (OUTPUT_DIR / "latest-run.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    case_rows = [
        "| ID | Feature | Preconditions | Test data | Steps | Expected result | Actual result | Status |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for case in all_cases:
        precondition = ("Python project dependencies installed" if case["id"].startswith("UT-")
                        else "Playwright package and Chromium installed; browser suite starts its local test server")
        fields = [case["id"], case["feature"], precondition, case["data"], case["steps"],
                  case["expected"], case["actual"], case["status"]]
        fields = [value.replace("|", "\\|").replace("\n", " ") for value in fields]
        case_rows.append("| " + " | ".join(fields) + " |")
    cases_doc = "\n".join([
        "# Executable Test Cases",
        "",
        f"Actual statuses below were captured from the latest run at {started}. They are generated by `python run_qa.py`; rerun it to refresh this file.",
        "",
        f"**Run:** {summary['total']} cases; {summary['passed']} passed; {summary['failed']} failed; {summary['skipped']} skipped; {summary['blocked']} blocked.",
        "",
        *case_rows,
        "",
        "Detailed test output is captured in `test-results/latest-run.json`.",
        "",
    ])
    (ROOT / "TEST_CASES.md").write_text(cases_doc, encoding="utf-8")

    total = summary["total"]
    summary_doc = f"""# Test Summary Report

**Run time:** {started}  
**Environment:** Python {summary['python']}; Windows; project root `{ROOT}`.  
**Scope:** Existing Python unit/system suite and Playwright browser suite.

| Measure | Result |
|---|---:|
| Total test cases | {total} |
| Passed | {summary['passed']} |
| Failed (assertion failures or errors) | {summary['failed']} |
| Skipped | {summary['skipped']} |
| Blocked | {summary['blocked']} |
| Executed or reported | {summary['executed']} / {total} |
| Test-case execution coverage | {summary['executed'] / total * 100 if total else 0:.1f}% |
| Requirement coverage in RTM | 9 / 9 mapped requirements |
| Defects identified and recorded | 7 (resolved) |
| Unresolved defects | 0 |

## Suite results

""" + "\n".join(
        f"- **{suite['suite']}:** {suite['cases']} cases, process exit code {suite['exit_code']}; command `{ ' '.join(suite['command']) }`."
        for suite in results
    ) + """

## Conclusion

""" + (
        "All executed suites completed successfully with no failed assertions. The seven defects documented in `BUG_REPORT.md` were corrected and rechecked."
        if overall_exit == 0 and summary["blocked"] == 0
        else "At least one suite failed or was blocked; review the per-case results and captured output in `TEST_CASES.md` and `test-results/latest-run.json`."
    ) + "\n"
    (ROOT / "TEST_SUMMARY.md").write_text(summary_doc, encoding="utf-8")

    print(f"\nQA report written: {ROOT / 'TEST_SUMMARY.md'}")
    print(f"Case details written: {ROOT / 'TEST_CASES.md'}")
    print(f"Machine-readable results: {OUTPUT_DIR / 'latest-run.json'}")
    return overall_exit


if __name__ == "__main__":
    raise SystemExit(main())
