"""Check the local submission evidence without rerunning benchmarks."""
import csv
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports"


def read(name):
    return json.loads((REPORTS / name).read_text(encoding="utf-8"))


def main():
    for name in ("06-lab-complete/check_production_ready.py",
                 "06-lab-complete/benchmark-observability/develop/eval/golden_dataset.jsonl"):
        original = subprocess.check_output(["git", "show", "HEAD:" + name], cwd=ROOT)
        assert (ROOT / name).read_bytes().replace(b"\r\n", b"\n") == original.replace(b"\r\n", b"\n"), name
    grader = (REPORTS / "production_ready.txt").read_text(encoding="utf-8")
    assert "PASS 12/12" in grader and "41/41 checks passed" in grader
    fixed = read("eval_v2_fixed.json")
    assert fixed["passed"] == fixed["total"] == 23
    assert fixed["quality_gate"]["passed"] and not fixed["quality_gate"]["regressions"]
    for name in [f"load_v2_c{c}.json" for c in (1, 10, 50, 100)] + [f"load_v2_slow_{r}.json" for r in ("0", "0.03", "0.1")]:
        report = read(name)
        assert report["total_requests"] == 300
        assert sum(report["status_codes"].values()) == 300
    for count in (1, 3):
        ids = (REPORTS / f"scale_{count}_containers.txt").read_text(encoding="utf-8").strip().splitlines()
        assert len(ids) == count
        relative = Path(f"benchmark-results/scale_{count}_stats.csv")
        primary = ROOT / "06-lab-complete/benchmark-observability/production" / relative
        assert (ROOT / relative).read_bytes() == primary.read_bytes()
        with (ROOT / relative).open(encoding="utf-8-sig", newline="") as file:
            rows = list(csv.DictReader(file))
        assert next(r for r in rows if r["Name"] == "/ask")["Request Count"] != "0"
    observations = read("alerts_errors_and_slow.json")["observations"]
    assert any(len([a for a in observation["alerts"] if a["state"] == "firing"]) >= 2 for observation in observations)
    for kind in ("slow", "error"):
        trace = read(f"jaeger_{kind}_trace.json")
        logs = read(f"jaeger_{kind}_logs.json")
        assert trace["spans"] and any(log["trace_id"] == trace["traceID"] for log in logs)
        read(f"jaeger_{kind}_trace_otlp.json")
        if kind == "error":
            assert any(field["value"] == "exception" for span in trace["spans"] for event in span["logs"] for field in event["fields"])
    for filename in ("grafana-dashboard.png", "prometheus-alert-firing.png", "jaeger-slow-trace.png", "jaeger-error-trace.png"):
        assert (ROOT / "screenshots" / filename).read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
    assert (ROOT / "DEPLOYMENT.md").exists()
    print("Local artifacts valid: grader, protected files, 7 load tests, eval, scaling, alerts, traces, screenshots")
    print("Cloud verification is recorded separately in DEPLOYMENT.md")


if __name__ == "__main__":
    main()
