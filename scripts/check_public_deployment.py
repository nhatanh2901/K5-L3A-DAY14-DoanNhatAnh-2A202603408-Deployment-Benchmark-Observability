"""Verify a real public agent without printing or retaining its API key."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True)
    parser.add_argument("--key-file", help="Ignored local JSON file containing agent_api_key")
    args = parser.parse_args()
    key = os.environ.get("AGENT_API_KEY", "")
    if args.key_file:
        key = json.loads(Path(args.key_file).read_text(encoding="utf-8"))["agent_api_key"]
    if not key:
        raise SystemExit("Set AGENT_API_KEY privately or pass --key-file")
    base = args.url.rstrip("/")
    results = []
    for method, path, authenticated, expected in (
        ("GET", "/health", False, 200), ("GET", "/ready", False, 200),
        ("POST", "/ask", False, 401), ("POST", "/ask", True, 200),
    ):
        headers = {"Content-Type": "application/json"}
        if authenticated:
            headers["X-API-Key"] = key
        data = json.dumps({"question": "Hello"}).encode() if method == "POST" else None
        request = urllib.request.Request(base + path, data=data, headers=headers, method=method)
        try:
            response = urllib.request.urlopen(request, timeout=120)
        except urllib.error.HTTPError as error:
            response = error
        with response:
            status = response.status
            body = response.read().decode("utf-8", errors="replace")
        record = {"method": method, "path": path, "authenticated": authenticated,
                  "status": status, "expected": expected, "passed": status == expected,
                  "body": body}
        results.append(record)
        print(f"{method} {path} auth={authenticated}: {status} (expected {expected})")
    report = {"public_url": base, "checked_at": datetime.now(timezone.utc).isoformat(),
              "checks": results, "passed": all(r["passed"] for r in results)}
    (ROOT / "reports/public_deployment_checks.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    raise SystemExit(0 if report["passed"] else 1)


if __name__ == "__main__":
    main()
