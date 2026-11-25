"""Retain measurement environment without account or host identifiers."""
import json
from pathlib import Path
import subprocess

info = json.loads(subprocess.check_output(["docker", "info", "--format", "{{json .}}"], text=True))
selected = {"cpus": info["NCPU"], "memory_bytes": info["MemTotal"],
            "os": info["OperatingSystem"], "server_version": info["ServerVersion"]}
root = Path(__file__).resolve().parents[1]
(root / "reports/environment.json").write_text(json.dumps(selected, indent=2), encoding="utf-8")
print("Recorded Docker CPUs/RAM/version")
