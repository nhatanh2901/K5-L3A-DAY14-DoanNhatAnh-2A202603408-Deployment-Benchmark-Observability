"""Collect Locust CSV, trace JSON, alerts and real browser screenshots locally."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
OBS = ROOT / "06-lab-complete/benchmark-observability/production"
REPORTS = ROOT / "reports"
COMPOSE = ["docker", "compose", "--progress", "plain", "-p", "k5-day14-observability", "-f", str(OBS / "docker-compose.yml")]
ENV = dict(os.environ)


def run(args, name, check=True):
    print(f"Running {name}", flush=True)
    result = subprocess.run(args, cwd=ROOT, env=ENV, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace")
    (REPORTS / f"{name}.txt").write_text(result.stdout, encoding="utf-8")
    if check and result.returncode:
        raise RuntimeError(f"{name}: {result.stdout[-2000:]}")
    return result


def get(url):
    with urllib.request.urlopen(url, timeout=15) as response:
        return json.load(response)


def screenshot(kind, trace=None):
    args = ["node", "scripts/capture_observability.cjs", kind]
    if trace:
        args.append(trace)
    run(args, f"screenshot_{kind}")


def locust(name, duration="2m"):
    return run(COMPOSE + ["run", "--rm", "--no-deps", "locust", "-f", "/mnt/locust/locustfile.py", "--host", "http://nginx",
                          "--headless", "-u", "100", "-r", "10", "-t", duration,
                          "--csv", f"/mnt/results/{name}"], name, check=False)


def alerts():
    return get("http://localhost:9090/api/v1/alerts")["data"]["alerts"]


def fault(name, variables, duration=200, pause=None):
    ENV.update(variables)
    run(COMPOSE + ["up", "-d", "--scale", "agent=3", "agent"], f"configure_{name}")
    # Allow DNS refresh before timing the actual experiment.
    time.sleep(12)
    started = time.time()
    if pause:
        run(["docker", "pause", pause], f"pause_{name}")
    logfile = open(REPORTS / f"fault_{name}_locust.txt", "w", encoding="utf-8")
    proc = subprocess.Popen(COMPOSE + ["run", "--rm", "--no-deps", "locust", "-f", "/mnt/locust/locustfile.py", "--host", "http://nginx",
                                      "--headless", "-u", "100", "-r", "10", "-t", f"{duration}s"],
                            cwd=ROOT, env=ENV, stdout=logfile, stderr=subprocess.STDOUT)
    records = []
    first_firing = {}
    captured = False
    try:
        while proc.poll() is None:
            current = alerts()
            elapsed = round(time.time() - started, 2)
            records.append({"elapsed_s": elapsed, "alerts": current})
            firing = {a["labels"]["alertname"] for a in current if a["state"] == "firing"}
            for alert in firing:
                first_firing.setdefault(alert, elapsed)
            (REPORTS / f"alerts_{name}.json").write_text(json.dumps({
                "variables": variables, "duration_s": elapsed,
                "first_observed_firing_s": first_firing, "observations": records}, indent=2), encoding="utf-8")
            if name == "errors_and_slow" and len(firing) >= 2 and not captured:
                screenshot("alerts")
                screenshot("grafana")
                captured = True
            print(f"Experiment {name}: {elapsed}s; firing={sorted(firing)}", flush=True)
            time.sleep(5)
        proc.wait()
    finally:
        if pause:
            run(["docker", "unpause", pause], f"unpause_{name}")
        if proc.poll() is None:
            proc.terminate()
        logfile.close()
    report = {"variables": variables, "duration_s": round(time.time() - started, 2),
              "first_observed_firing_s": first_firing, "observations": records}
    (REPORTS / f"alerts_{name}.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def traces():
    # BatchSpanProcessor exports asynchronously; wait for the final requests.
    time.sleep(6)
    logs = run(COMPOSE + ["logs", "--no-color", "agent"], "observability_agent_logs").stdout
    objects = []
    for line in logs.splitlines():
        pos = line.find('{"ts"')
        if pos >= 0:
            try:
                objects.append(json.loads(line[pos:]))
            except ValueError:
                pass
    slow = max((o for o in objects if o.get("event") == "llm_call"), key=lambda o: o["llm_ms"])
    error = next(o for o in reversed(objects) if o.get("event") == "llm_error")
    for kind, obj in (("slow", slow), ("error", error)):
        trace_id = obj["trace_id"]
        raw = get(f"http://localhost:16686/api/v3/traces/{trace_id}")
        (REPORTS / f"jaeger_{kind}_trace_otlp.json").write_text(json.dumps(raw, indent=2), encoding="utf-8")
        # Normalize only field names/time units for the report renderer; retain
        # the complete original OTLP response above as primary evidence.
        spans = []
        resource_spans = raw.get("result", raw).get("resourceSpans", [])
        for resource in resource_spans:
            for scope in resource.get("scopeSpans", []):
                for s in scope.get("spans", []):
                    spans.append({"operationName": s["name"],
                                  "startTime": int(s["startTimeUnixNano"]) / 1000,
                                  "duration": (int(s["endTimeUnixNano"]) - int(s["startTimeUnixNano"])) / 1000,
                                  "logs": [{"fields": [{"key": "event", "value": e["name"]}]}
                                           for e in s.get("events", [])],
                                  "status": s.get("status", {})})
        trace = {"traceID": trace_id, "source": "Jaeger v3 OTLP HTTP API", "spans": spans}
        (REPORTS / f"jaeger_{kind}_trace.json").write_text(json.dumps(trace, indent=2), encoding="utf-8")
        matching = [entry for entry in objects if entry.get("trace_id") == trace_id]
        (REPORTS / f"jaeger_{kind}_logs.json").write_text(json.dumps(matching, indent=2, ensure_ascii=False), encoding="utf-8")
        screenshot(kind, trace_id)


def main():
    for attempt in range(60):
        try:
            health = get("http://localhost:8080/health")
            break
        except OSError:
            time.sleep(1)
    else:
        raise RuntimeError("Agent not healthy after 60 seconds")
    (REPORTS / "observability_health.json").write_text(json.dumps(health), encoding="utf-8")
    if "--large-model" in sys.argv:
        fault("large_model", {"MOCK_ERROR_RATE": "0.01", "MOCK_SLOW_RATE": "0.03", "LLM_MODEL": "mock-llm-large"}, duration=180)
        traces()
        ENV["LLM_MODEL"] = "mock-llm-small"
        run(COMPOSE + ["up", "-d", "--scale", "agent=3", "agent"], "restore_small_model")
        return
    if "--faults" in sys.argv:
        ENV.update({"MOCK_ERROR_RATE": "0.01", "MOCK_SLOW_RATE": "0.03", "LLM_MODEL": "mock-llm-small"})
        run(COMPOSE + ["up", "-d", "--scale", "agent=3", "agent"], "fault_reset_setup")
        time.sleep(12)
        locust("fault_reset", duration="75s")
        fault("errors_and_slow", {"MOCK_ERROR_RATE": "0.2", "MOCK_SLOW_RATE": "0.3"}, duration=200)
        traces()
        fault("large_model", {"MOCK_ERROR_RATE": "0.01", "MOCK_SLOW_RATE": "0.03", "LLM_MODEL": "mock-llm-large"}, duration=180)
        return
    if "--finish" in sys.argv:
        # Resume after collecting A/B/C, rerun scaling with --no-deps so Compose
        # cannot reset the requested scale to deploy.replicas=2.
        ENV.update({"AGENT_VERSION": "v2", "MOCK_ERROR_RATE": "0.01", "MOCK_SLOW_RATE": "0.03", "LLM_MODEL": "mock-llm-small"})
        for count in (1, 3):
            run(COMPOSE + ["up", "-d", "--scale", f"agent={count}"], f"scale_{count}_setup")
            time.sleep(12)
            listing = run(COMPOSE + ["ps", "-q", "agent"], f"scale_{count}_containers")
            if len(listing.stdout.strip().splitlines()) != count:
                raise RuntimeError("Unexpected number of agent containers")
            locust(f"scale_{count}")
        for path in (OBS / "benchmark-results").glob("*.csv"):
            shutil.copy2(path, ROOT / "benchmark-results" / path.name)
        fault("instance_down", {"LLM_MODEL": "mock-llm-small", "MOCK_ERROR_RATE": "0.01", "MOCK_SLOW_RATE": "0.03"},
              duration=65, pause="k5-day14-observability-agent-3")
        print("Scaling and instance-down experiment collected", flush=True)
        return
    if "--semantic" in sys.argv:
        ENV.update({"AGENT_VERSION": "v1", "MOCK_ERROR_RATE": "0.01", "MOCK_SLOW_RATE": "0.03", "LLM_MODEL": "mock-llm-small"})
        run(COMPOSE + ["up", "-d", "--scale", "agent=3", "agent"], "configure_v1")
        time.sleep(12)
        run(["docker", "run", "--rm", "--network", "host", "-v", f"{ROOT}:/workspace",
             "-w", "/workspace/06-lab-complete/benchmark-observability/develop", "k5-day14-lab-runner",
             "python", "eval/run_eval.py", "--url", "http://localhost:8080", "--api-key", "day14-lab-key",
             "--out", "/workspace/reports/eval_production_v1.json"], "eval_production_v1", check=False)
        ENV["AGENT_VERSION"] = "v2"
        run(COMPOSE + ["up", "-d", "--scale", "agent=3", "agent"], "restore_v2")
        return
    run(COMPOSE + ["up", "-d", "--scale", "agent=1"], "scale_1_setup")
    locust("scale_1")
    screenshot("grafana")
    run(COMPOSE + ["up", "-d", "--scale", "agent=3"], "scale_3_setup")
    time.sleep(12)
    locust("scale_3")
    for path in (OBS / "benchmark-results").glob("*.csv"):
        shutil.copy2(path, ROOT / "benchmark-results" / path.name)
    fault("errors_and_slow", {"MOCK_ERROR_RATE": "0.2", "MOCK_SLOW_RATE": "0.3"}, duration=200)
    traces()
    fault("large_model", {"MOCK_ERROR_RATE": "0.01", "MOCK_SLOW_RATE": "0.03", "LLM_MODEL": "mock-llm-large"}, duration=180)
    fault("instance_down", {"LLM_MODEL": "mock-llm-small", "MOCK_ERROR_RATE": "0.01", "MOCK_SLOW_RATE": "0.03"},
          duration=65, pause="k5-day14-observability-agent-3")
    # Semantic failures: metric-based latency/error alerts cannot establish correctness.
    ENV["AGENT_VERSION"] = "v1"
    run(COMPOSE + ["up", "-d", "--scale", "agent=3", "agent"], "configure_v1")
    time.sleep(12)
    run(["docker", "run", "--rm", "--network", "host", "-v", f"{ROOT}:/workspace",
         "-w", "/workspace/06-lab-complete/benchmark-observability/develop", "k5-day14-lab-runner",
         "python", "eval/run_eval.py", "--url", "http://localhost:8080", "--api-key", "day14-lab-key",
         "--out", "/workspace/reports/eval_production_v1.json"], "eval_production_v1", check=False)
    ENV.update({"AGENT_VERSION": "v2", "MOCK_ERROR_RATE": "0.01", "MOCK_SLOW_RATE": "0.03", "LLM_MODEL": "mock-llm-small"})
    run(COMPOSE + ["up", "-d", "--scale", "agent=3", "agent"], "restore_v2")
    print("Observability evidence collected", flush=True)


if __name__ == "__main__":
    main()
