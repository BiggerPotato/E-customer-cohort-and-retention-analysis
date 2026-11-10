# Test Plan — Retention Studio

## Document control

| Field | Value |
|---|---|
| Project | Ecommerce Customer Retention and Cohort Analysis |
| Version | 2.0 — assessment update |
| Test approach | Python `unittest` + Playwright for Python/Chromium |
| Primary test data | `Online Retail.csv` and deterministic in-memory browser fixtures |
| Related artifacts | `TEST_CASES.md`, `BUG_REPORT.md`, `RTM.md`, `TEST_SUMMARY.md`, `CODE_ANALYSIS.md` |

## Objectives

- Verify transaction cleaning, revenue calculation, repeat-customer logic, cohort indexing, and generated output files.
- Exercise valid, invalid, missing, boundary, and representative transaction inputs.
- Verify the local dashboard reads the project CSV files, renders revenue and cohort charts, reports customer metrics, supports refresh, and explains missing files.
- Record defects with reproducible evidence and trace application requirements to executable cases.

## Application modules and scope

| Module | Included functionality |
|---|---|
| `retention_helpers.py` | Transaction validation, invoice cancellation filtering, revenue calculation, cohort month index. |
| `retention_analysis.py` | CSV load, aggregation by customer/invoice/month, cohort retention, summary output, PNG charts. |
| `index.html`, `styles.css`, `script.js` | Responsive dashboard, CSV parsing, key metrics, revenue chart, cohort heatmap, refresh, test results. |
| `dashboard_server.py` | Local static file server and endpoints that execute the Python suites. |
| `test_retention_analysis.py` | Existing unit, integration, and full-program output tests. |
| `test_dashboard_browser.py` | Playwright end-to-end browser checks using a local server and a small deterministic source-data fixture. |

Out of scope: deployment to a public host, authentication, database behavior (none exists), load/performance testing, and proving causes of customer behavior.

## Testing strategy

1. **Equivalence partitioning:** valid purchases, cancelled invoices, returns/nonpositive quantities, nonpositive prices, missing fields, and malformed dates.
2. **Boundary value analysis:** quantity 0, negative, fractional-positive; price 0, negative, small positive; non-finite price; same/next month and year-boundary cohort indexes.
3. **Positive and negative testing:** accepted valid purchase and revenue; rejected invalid/cancelled input; dashboard loads valid outputs and presents an error if a required CSV is unavailable.
4. **Functional/unit testing:** revenue, cleaner, cohort index, repeat classification.
5. **Integration/system testing:** clean → calculate → aggregate, full analysis script, creation of both CSVs and all three PNGs (combined report, dedicated order-gap chart, and cohort heatmap).
6. **Browser automation:** Playwright verifies rendered UI, summary-backed charts, source-record metrics, refresh, clear missing-file error, and the embedded test runner.
7. **Code analysis:** review the script/helper call path and frontend/server data flow; Python compile check, JavaScript syntax check, and executable regression tests. Findings are in `CODE_ANALYSIS.md`.

## Environment and resources

- Windows 11, Python 3.14.2, local VS Code terminal.
- Existing packages from `requirements.txt`: pandas, matplotlib, seaborn.
- Browser automation package: `playwright==1.64.1`; browser: Playwright-managed Chromium.
- Project dataset: `Online Retail.csv` (actual project source); generated summaries and charts are local outputs.
- No database or remote service is used. Browser tests create a temporary localhost server and use an in-memory 3-order fixture for metric assertions; the Python system test runs the actual project CSV.

Install/run commands are listed in `README_DASHBOARD.md` and `RUNBOOK_DEMO.md`.

## Entry criteria

- Project source and `Online Retail.csv` are available in the project folder.
- Python dependencies are installed.
- For browser tests, Playwright and its Chromium browser are installed.
- No other process is using the selected demo port 8000 (browser test server selects an ephemeral port).

## Exit criteria

- All required test cases have an actual recorded status.
- Failures are investigated; unresolved findings remain listed in the bug report and summary.
- The analysis generates the two CSVs and three PNG outputs, including the dedicated order-gap image used in the dashboard.
- The dashboard passes the Playwright checks for its core behaviors.
- Test summary identifies totals, coverage, and remaining limitations.

## Risks and mitigation

| Risk | Mitigation |
|---|---|
| The source CSV is large and can slow analysis/browser startup. | Run locally; browser automation uses a small deterministic fixture except for the existing Python system test. |
| Opening `index.html` as a `file://` page blocks CSV fetches. | Run `python dashboard_server.py` and use `http://127.0.0.1:8000`. |
| Browser automation may fail when Chromium is not installed. | Install it once with `python -m playwright install chromium`; report setup errors as blocked, not passed. |
| Later cohort periods are unavailable for newer cohorts. | Display blank heatmap cells and document the observation-window limitation. |
| Small sample fixtures may not represent all retail data edge cases. | Keep the actual CSV system test and existing unit regression tests in the verification run. |

## Test evidence

The latest executed case-level results are generated in `TEST_CASES.md`; the dated run summary is in `TEST_SUMMARY.md`; raw machine-readable output is `test-results/latest-run.json`. Run `python run_qa.py` to refresh all three from a new actual execution.
