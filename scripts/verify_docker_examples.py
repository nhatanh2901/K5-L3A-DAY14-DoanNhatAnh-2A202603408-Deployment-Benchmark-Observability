"""Save real Part 2 HTTP responses and Docker image sizes."""
import json
from pathlib import Path
import subprocess
import time
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]

def request(url, body=None):
    req = urllib.request.Request(url, data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Content-Type": "application/json"},
                                 method="POST" if body is not None or "/ask" in url else "GET")
    for _ in range(120):
        try:
            with urllib.request.urlopen(req, timeout=5) as response:
                return {"url": url, "status": response.status, "body": json.load(response)}
        except (OSError, ValueError):
            time.sleep(1)
    raise RuntimeError(f"Cannot call {url}")

result = {"develop": request("http://localhost:18000/ask?question=Hello"),
          "nginx_health": request("http://localhost/health"),
          "nginx_ask": request("http://localhost/ask", {"question": "Explain microservices"})}
raw = subprocess.check_output(["docker", "image", "inspect", "my-agent:develop", "my-agent:advanced"], text=True)
images = json.loads(raw)
result["images"] = [{"tags": item["RepoTags"], "size_bytes": item["Size"], "size_mib": round(item["Size"] / 1024**2, 2)} for item in images]
result["size_reduction_percent"] = round((1 - images[1]["Size"] / images[0]["Size"]) * 100, 2)
(ROOT / "reports/docker_examples.json").write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
print(json.dumps(result, ensure_ascii=True, indent=2))
