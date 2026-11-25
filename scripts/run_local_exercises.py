"""Run the supplied examples in isolated subprocesses and save redacted evidence."""
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
import time
from contextlib import contextmanager

import httpx

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports"
REPORTS.mkdir(exist_ok=True)


@contextmanager
def server(folder, port, **env):
    path = ROOT / folder
    # All examples use utils.mock_llm; resolve their local copy first, root second.
    config = {**os.environ, "PYTHONPATH": f"{path}:{ROOT}", "PORT": str(port), **env}
    with open(REPORTS / f"server_{port}.log", "w", encoding="utf-8") as log:
        proc = subprocess.Popen([sys.executable, "-m", "uvicorn", "app:app", "--host",
                                 "0.0.0.0", "--port", str(port)], cwd=path,
                                env=config, stdout=log, stderr=log)
        try:
            with httpx.Client(base_url=f"http://127.0.0.1:{port}", timeout=15) as client:
                for _ in range(100):
                    if proc.poll() is not None:
                        raise RuntimeError(f"Server failed: {folder}; see server_{port}.log")
                    try:
                        if client.get("/openapi.json").status_code == 200:
                            break
                    except httpx.HTTPError:
                        pass
                    time.sleep(0.1)
                else:
                    raise RuntimeError(f"Server timeout: {folder}")
                yield client
        finally:
            proc.terminate()
            try:
                proc.wait(15)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()


def evidence(response):
    return {"status": response.status_code, "headers": dict(response.headers),
            "body": response.json()}


def basics():
    results = {}
    with server("01-localhost-vs-production/develop", 8101) as c:
        results["part1_develop"] = evidence(c.post("/ask", params={"question": "Hello"}))
    with server("01-localhost-vs-production/production", 8102) as c:
        results["part1_production"] = evidence(c.post("/ask", json={"question": "Hello"}))
        results["part1_health"] = evidence(c.get("/health"))
    key = secrets.token_hex(24)
    with server("04-api-gateway/develop", 8104, AGENT_API_KEY=key) as c:
        results["part4_missing"] = evidence(c.post("/ask", json={"question": "Hello"}))
        results["part4_authorized"] = evidence(c.post("/ask", json={"question": "Hello"}, headers={"X-API-Key": key}))
    with server("04-api-gateway/production", 8105, JWT_SECRET=secrets.token_hex(32)) as c:
        token_response = c.post("/auth/token", json={"username": "student", "password": "demo123"})
        token_response.raise_for_status()
        results["part4_login"] = {"status": token_response.status_code, "token": "[REDACTED]"}
        token = token_response.json()["access_token"]
        results["part4_burst"] = [evidence(c.post("/ask", json={"question": "What is Docker?"},
                                                       headers={"Authorization": f"Bearer {token}"}))
                                  for _ in range(15)]
    with server("05-scaling-reliability/develop", 8106) as c:
        results["part5_health"] = evidence(c.get("/health"))
        results["part5_ready"] = evidence(c.get("/ready"))
    (REPORTS / "local_exercises.json").write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    # The intentionally unsafe Part 1 develop app prints its fake secret: retain
    # HTTP evidence but remove the demonstration credential from collected logs.
    log = REPORTS / "server_8101.log"
    log.write_text("\n".join(line for line in log.read_text().splitlines() if "Using key:" not in line), encoding="utf-8")
    print("Part 1, 4, 5 evidence saved", flush=True)


def benchmark():
    folder = "06-lab-complete/benchmark-observability/develop"
    cwd = ROOT / folder

    def run(*args):
        completed = subprocess.run([sys.executable, *args], cwd=cwd)
        if completed.returncode not in (0, 1):
            raise RuntimeError(f"Command failed: {args}")

    with server(folder, 8001, AGENT_VERSION="v1"):
        run("eval/run_eval.py", "--url", "http://localhost:8001", "--out", "reports/eval_v1.json")
    with server(folder, 8002, AGENT_VERSION="v2"):
        run("eval/run_eval.py", "--url", "http://localhost:8002", "--out", "reports/eval_v2.json")
        for concurrency in (1, 10, 50, 100):
            run("load_test.py", "--url", "http://localhost:8002", "--requests", "300",
                "--concurrency", str(concurrency), "--out", f"reports/load_v2_c{concurrency}.json")
    for rate in ("0", "0.03", "0.1"):
        with server(folder, 8002, AGENT_VERSION="v2", MOCK_SLOW_RATE=rate):
            run("load_test.py", "--url", "http://localhost:8002", "--requests", "300",
                "--concurrency", "20", "--out", f"reports/load_v2_slow_{rate}.json")
    import shutil
    for path in (cwd / "reports").glob("*.json"):
        shutil.copy2(path, REPORTS / path.name)


if __name__ == "__main__":
    if "--fixed-eval" in sys.argv:
        folder = "06-lab-complete/benchmark-observability/develop"
        with server(folder, 8002, AGENT_VERSION="v2"):
            subprocess.run([sys.executable, "eval/run_eval.py", "--url", "http://localhost:8002",
                            "--min-accuracy", "1.0", "--baseline", "reports/eval_v2.json",
                            "--out", "reports/eval_v2_fixed.json"], cwd=ROOT / folder, check=True)
        import shutil
        shutil.copy2(ROOT / folder / "reports/eval_v2_fixed.json", REPORTS / "eval_v2_fixed.json")
    elif "--benchmark" in sys.argv:
        benchmark()
    else:
        basics()
