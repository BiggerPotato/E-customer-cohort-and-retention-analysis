"""Serve the static dashboard and run the existing unittest suite on request."""

from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import json
import re
import subprocess
import sys
import importlib.util
from urllib.parse import urlsplit


ROOT = Path(__file__).resolve().parent
CASE_LINE = re.compile(r"^(test\w+) \(([^)]+)\) \.\.\. (ok|FAIL|ERROR|skipped.*)$")
PYTEST_LINE = re.compile(r"^(test_retention_analysis\.py::.+?)\s+(PASSED|FAILED|ERROR|SKIPPED|XFAIL|XPASS)(?:\s|$)")


class DashboardHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def do_GET(self):
        endpoint = urlsplit(self.path).path
        if endpoint not in {"/api/tests", "/api/browser-tests"}:
            return super().do_GET()

        try:
            if endpoint == "/api/browser-tests":
                command = [sys.executable, "-m", "unittest", "-v", "test_dashboard_browser"]
            else:
                command = ([sys.executable, "-m", "pytest", "-v", "test_retention_analysis.py"]
                           if importlib.util.find_spec("pytest")
                           else [sys.executable, "-m", "unittest", "-v", "test_retention_analysis"])
            result = subprocess.run(
                command,
                cwd=ROOT,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                timeout=120,
                check=False,
            )
            output = result.stdout or ""
            cases = []
            for line in output.splitlines():
                match = CASE_LINE.match(line.strip())
                if match:
                    method, qualified, status = match.groups()
                    state = "skipped" if status.startswith("skipped") else ("passed" if status == "ok" else "failed")
                    name = qualified if qualified.endswith(f".{method}") else f"{qualified}.{method}"
                    cases.append({"name": name, "status": state})
                    continue
                match = PYTEST_LINE.match(line.strip())
                if match:
                    name, status = match.groups()
                    state = "passed" if status == "PASSED" else "skipped" if status in {"SKIPPED", "XFAIL"} else "failed"
                    cases.append({"name": name, "status": state})
            payload = {
                "success": result.returncode == 0,
                "cases": cases,
                "passed": sum(case["status"] == "passed" for case in cases),
                "failed": sum(case["status"] == "failed" for case in cases),
                "skipped": sum(case["status"] == "skipped" for case in cases),
                "output": output[-12000:],
            }
        except subprocess.TimeoutExpired as exc:
            payload = {"success": False, "cases": [], "passed": 0, "failed": 0, "skipped": 0,
                       "output": f"The test run exceeded the 120 second limit.\n{exc}"}
        except Exception as exc:
            payload = {"success": False, "cases": [], "passed": 0, "failed": 0, "skipped": 0,
                       "output": f"Could not run the existing tests: {exc}"}

        body = json.dumps(payload).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)


if __name__ == "__main__":
    server = ThreadingHTTPServer(("127.0.0.1", 8000), DashboardHandler)
    print("Dashboard ready at http://127.0.0.1:8000")
    print("Press Ctrl+C to stop the server.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nDashboard server stopped.")
        server.server_close()
