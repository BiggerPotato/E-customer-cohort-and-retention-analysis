# Code Analysis Findings

## Review method and tools

- Manual control/data-flow review of `retention_analysis.py`, `retention_helpers.py`, `dashboard_server.py`, and the HTML/CSS/JavaScript dashboard.
- Python syntax/bytecode check: `python -m compileall -q retention_analysis.py retention_helpers.py dashboard_server.py test_dashboard_browser.py`.
- JavaScript syntax check: `node --check script.js`.
- Dynamic regression confirmation: `python -m unittest -v test_retention_analysis.py`.
- Browser behavior confirmation: `python -m unittest -v test_dashboard_browser.py` using Playwright and Chromium.

Both syntax commands completed successfully. Regression and browser outcomes are generated from actual test runs in `TEST_SUMMARY.md`.

## Findings

| Finding | Evidence / impact | Change or disposition |
|---|---|---|
| Cancellation invoice normalization was case-sensitive and did not trim whitespace. | `str.startswith("C")` rejected only uppercase prefixes at the first character; `c1001` and ` C1001` survived. | Helper now trims IDs and compares an uppercase prefix; regression cases prove both invalid forms are removed. |
| Non-finite numeric values passed positivity validation. | `float("inf") > 0` evaluates true and would inflate revenue/averages. | Cleaner now requires finite price and quantity values before positive-range validation. |
| Analysis script and helper duplicated row cleaning. | The script called `clean_transactions` and then applied a second direct filter/revenue calculation; tested helper and production path could diverge. | Removed the second filter and use `calculate_revenue` from the shared helper. |
| UI's guessed source-file candidates missed the project's real file/schema. | Actual data is `Online Retail.csv`, with headers `CustomerID`, `InvoiceNo`, `InvoiceDate`, `Quantity`, and `UnitPrice`. Missing aliases prevented source metrics. | Add actual filename and camel-case normalized invoice/date aliases. Browser test verifies resulting metrics. |
| Cohort CSV is wide-form with numeric columns (`0`, `1`, …), while the browser parser expected tidy period/value columns. | Existing CSV had `CohortMonth,0,1,...`; parser fell back to PNG instead of rendering a grid. | Numeric month columns are recognized and rendered; browser test checks month 0 and cohort rows. |
| Test result renderer duplicated the method suffix. | Qualified unittest ID already ended in the method name. | Keep the qualified name once; case list verified through the dashboard test. |
| The days-between-orders panel reused a combined two-plot PNG. | `retention_analysis.png` contains both monthly revenue and order-gap plots, which made revenue appear in the wrong dashboard section. | Generate `days_between_orders.png` separately; the dashboard references that image only in the order-gap panel. Browser checks verify the revenue canvas has blue plotted pixels and the gap panel loads the dedicated PNG. |

## Remaining maintainability notes

- The dashboard's CSV parser is intentionally a small project-local parser. If the app later accepts arbitrary quoted CSV dialects, replace it with a maintained parser or perform CSV normalization server-side.
- The backend test endpoint executes local test modules on user action and is intended for localhost demonstration, not public deployment.
- The generated cohort output has missing future periods by design; these cells should remain blank rather than being treated as zero retention.
