# Physical Examination Demonstration Runbook

## One-time setup

In VS Code, open this project folder, choose the intended Python interpreter, then open **Terminal → New Terminal**.

```powershell
python -m pip install -r requirements-test.txt
python -m playwright install chromium
```

The browser install needs internet access and is only needed once per machine.

## Demonstration sequence

### A. Generate the analysis artifacts

```powershell
$env:MPLBACKEND = "Agg"
python retention_analysis.py
```

Show `monthly_summary.csv`, `cohort_retention.csv`, `retention_analysis.png`, `days_between_orders.png`, and `cohort_retention_heatmap.png` in the project Explorer. The dashboard uses the dedicated order-gap PNG, so the combined analysis figure is not inserted into the days section.

### B. Run the Python tests

```powershell
python -m unittest -v test_retention_analysis.py
```

This runs 35 tests across transaction cleaning, boundary/invalid cases, revenue, cohort indexing, integration, and full-program outputs.

### C. Run the Playwright browser automation

```powershell
python -m unittest -v test_dashboard_browser.py
```

This starts a temporary local server, launches headless Chromium, verifies 35 dashboard browser cases, and shuts both down when complete. Checks cover actual project data, controlled positive/negative inputs, KPI cards, charts, cohort periods, responsive layout, error handling, and test-result presentation.

### D. Generate/update the assessment reports

```powershell
python run_qa.py
```

The command runs 35 Python tests and 35 Playwright browser tests, then writes actual per-case results to `TEST_CASES.md`, the run summary to `TEST_SUMMARY.md`, and machine-readable evidence to `test-results/latest-run.json`.

### E. Present the dashboard

In another VS Code terminal:

```powershell
python dashboard_server.py
```

Open <http://127.0.0.1:8000>. Use **Refresh data**, **Run Python tests**, and **Run browser tests** to demonstrate the app. The links in the Testing & Quality section open the test plan, cases, bug report, RTM, summary, and code-analysis findings.

## Stop

Press **Ctrl+C** in the terminal running `dashboard_server.py`. The temporary server used by Playwright is stopped automatically at the end of its run.
