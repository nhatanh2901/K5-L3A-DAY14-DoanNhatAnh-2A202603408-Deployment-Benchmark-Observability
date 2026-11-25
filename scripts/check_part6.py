"""Run the unmodified grader and retain its full stdout as submission evidence."""
from pathlib import Path
import subprocess
import sys

root = Path(__file__).resolve().parents[1]
result = subprocess.run([sys.executable, "check_production_ready.py", *sys.argv[1:]],
                        cwd=root / "06-lab-complete", text=True,
                        stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
(root / "reports").mkdir(exist_ok=True)
(root / "reports/production_ready.txt").write_text(result.stdout.rstrip() + "\n", encoding="utf-8")
print(result.stdout, end="")
raise SystemExit(result.returncode)
