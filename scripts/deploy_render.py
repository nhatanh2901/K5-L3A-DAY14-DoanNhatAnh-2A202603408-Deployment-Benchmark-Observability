"""Deploy the lab using Render CLI; retain credentials only in ignored files."""
import argparse
import json
from pathlib import Path
import secrets
import subprocess

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / ".lab-tools/render-cli/render.exe"
PRIVATE = ROOT / ".lab-tools/render-deployment.private.json"


def cli(*args):
    result = subprocess.run([str(CLI), *args, "--output", "json"], cwd=ROOT,
                            capture_output=True, text=True, encoding="utf-8")
    if result.returncode:
        raise RuntimeError(result.stderr[:1500])
    return json.loads(result.stdout)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["redis", "connection", "agent", "status", "inspect"])
    args = parser.parse_args()
    state = json.loads(PRIVATE.read_text(encoding="utf-8")) if PRIVATE.exists() else {}
    if args.action == "redis":
        if "redis" in state:
            raise SystemExit("Redis already recorded; inspect before creating another")
        state["redis"] = cli("keyvalues", "create", "--name", "k5-day14-redis", "--plan", "free",
                             "--region", "singapore", "--memory-policy", "noeviction",
                             "--persistence-mode", "off", "--confirm")
    elif args.action == "connection":
        redis_id = state["redis"]["data"]["id"]
        state["redis_details"] = cli("keyvalues", "get", redis_id, "--include-sensitive-connection-info")
    elif args.action == "agent":
        if "agent" in state:
            raise SystemExit("Agent already recorded; inspect before creating another")
        key = state.setdefault("agent_api_key", secrets.token_urlsafe(32))
        PRIVATE.write_text(json.dumps(state, indent=2), encoding="utf-8")
        redis_url = state["redis_details"]["data"]["connectionInfo"]["internalConnectionString"]
        state["agent"] = cli(
            "services", "create", "--name", "k5-day14-agent", "--type", "web_service",
            "--runtime", "docker", "--plan", "free", "--region", "singapore",
            "--repo", "https://github.com/nhatanh2901/K5-L3A-DAY14-DoanNhatAnh-2A202603408-Deployment-Benchmark-Observability",
            "--branch", "main", "--root-directory", "06-lab-complete",
            "--health-check-path", "/health", "--auto-deploy=false",
            "--env-var", "ENVIRONMENT=production", "--env-var", f"AGENT_API_KEY={key}",
            "--env-var", f"REDIS_URL={redis_url}", "--env-var", "RATE_LIMIT_PER_MINUTE=10",
            "--env-var", "DAILY_BUDGET_USD=1", "--env-var", "MONTHLY_BUDGET_USD=10", "--confirm")
    elif args.action == "status":
        state["deployments"] = cli("deploys", "list", state["agent"]["id"])
        (ROOT / "reports/render_deployments.json").write_text(json.dumps(state["deployments"], indent=2), encoding="utf-8")
        print("Deployment states:", [d["status"] for d in state["deployments"]])
    PRIVATE.write_text(json.dumps(state, indent=2), encoding="utf-8")
    for name, value in state.items():
        if isinstance(value, dict):
            print(name, "fields:", list(value))
            print({key: value[key] for key in ("id", "name", "plan", "status", "region") if key in value})
            for key, child in value.items():
                if isinstance(child, dict):
                    print(name, key, "fields:", list(child))


if __name__ == "__main__":
    main()
