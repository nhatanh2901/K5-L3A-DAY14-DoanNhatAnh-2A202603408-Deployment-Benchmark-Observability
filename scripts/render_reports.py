"""Render tables exclusively from retained measurements; mark absent evidence."""
import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports"


def read(name):
    path = REPORTS / name
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def main():
    environment_path = REPORTS / "environment.json"
    environment = json.loads(environment_path.read_text(encoding="utf-8-sig")) if environment_path.exists() else None
    lines = [
        "# Benchmark & Observability Report — Day 14", "",
        "**Họ tên:** DoanNhatAnh", "", "**Ngày chạy:** 25/11/2026 (GMT+7)", "",
        "**Môi trường:** Windows, Docker Desktop Linux, Python 3.11 trong container; mock LLM. "
        "Host Python 3.13 chỉ điều phối Docker và lưu evidence, không chạy script chấm SIGTERM.", "",
        "Mọi số dưới đây đọc từ JSON/CSV trong repo. Các lần chạy là một lần đo, có ngẫu nhiên; "
        "không chứng minh hiệu năng của LLM/provider thật. Load test local ban đầu chạy cùng lúc với "
        "một số kiểm tra khác nên có thể bị ảnh hưởng bởi tranh chấp CPU/I/O.", "",
        "## 1. SLO của agent", "",
        "| SLI | SLO | Lý do |", "|---|---|---|",
        "| p95 `/ask` local | ≤ 500 ms | Ngưỡng mặc định của load_test.py |",
        "| Error rate local | ≤ 2% | Ngưỡng mặc định của load_test.py |",
        "| Accuracy eval sau sửa KB | 100%, không regression | Quality gate theo CP7 |", "",
        "Alert rules production là ngưỡng khác: error rate >5% trong 1 phút; p95 >1 giây trong "
        "2 phút; instance down 30 giây; cost burn >2 USD/giờ trong 2 phút.", "",
        "## 2. Benchmark hiệu năng", "", "### 2.1 Concurrency vs latency", "",
        "300 request mỗi mức; agent v2, default mock latency/jitter, slow rate 0.03 và error rate 0.01.", "",
        "| Concurrency | RPS | p50 ms | p95 ms | p99 ms | Error rate | SLO |",
        "|---|---:|---:|---:|---:|---:|---|",
    ]
    for c in (1, 10, 50, 100):
        r = read(f"load_v2_c{c}.json")
        if r:
            l = r["latency_ms"]
            lines.append(f"| {c} | {r['rps']} | {l['p50']} | {l['p95']} | {l['p99']} | {r['error_rate']:.2%} | {'PASS' if r['slo']['passed'] else 'FAIL'} |")
    lines += ["", "Nguồn: `reports/load_v2_c*.json`. Latency trong script chỉ tính các response 200; "
              "error rate tính toàn bộ request. Vì vậy cần đọc đồng thời cả hai chỉ số.", "",
              "RPS không tăng tuyến tính: concurrency 100 có RPS thấp hơn 50 và p95 tăng mạnh. "
              "Đây là quan sát trên môi trường đo này, có thể do tải đồng thời và scheduling; "
              "chưa đủ dữ liệu để khẳng định nút thắt CPU hay network. Không đổi số để ép SLO PASS.", "",
              "### 2.2 Tail latency", "", "Cùng 300 request và concurrency 20, restart agent mỗi mức slow rate.", "",
              "| MOCK_SLOW_RATE | avg ms | p95 ms | p99 ms |", "|---|---:|---:|---:|"]
    if environment:
        lines.insert(6, f"Docker engine {environment['server_version']}, {environment['cpus']} CPU, "
                     f"{environment['memory_bytes'] / 1024**3:.2f} GiB RAM được cấp cho Docker; "
                     "nguồn: reports/environment.json.\n")
    for rate in ("0", "0.03", "0.1"):
        r = read(f"load_v2_slow_{rate}.json")
        if r:
            l = r["latency_ms"]
            lines.append(f"| {rate} | {l['avg']} | {l['p95']} | {l['p99']} |")
    lines += ["", "Nguồn: `reports/load_v2_slow_*.json`. p99 nhạy với đuôi chậm ở mức 3%; "
              "khi khoảng 10% request chậm, p95 cũng tăng rõ. Average pha loãng trải nghiệm xấu "
              "của nhóm nhỏ người dùng; nên đặt SLO theo percentile và theo dõi error riêng.", "",
              "## 3. Benchmark chất lượng", "",
              "| Chỉ số | v1 | v2 ban đầu | v2 sửa KB |", "|---|---:|---:|---:|"]
    evals = [read(name) for name in ("eval_v1.json", "eval_v2.json", "eval_v2_fixed.json")]
    if all(evals):
        for label, fmt in (
            ("Accuracy", lambda r: f"{r['accuracy']:.1%} ({r['passed']}/{r['total']})"),
            ("Avg tokens/câu", lambda r: str(r["avg_tokens"])),
            ("Tổng cost USD", lambda r: str(r["total_cost_usd"])),
            ("Cost/câu đúng USD", lambda r: str(r["cost_per_correct_usd"])),
            ("p95 ms", lambda r: str(r["latency_ms"]["p95"])),
            ("Quality gate", lambda r: "PASS" if r["quality_gate"]["passed"] else "FAIL"),
        ):
            lines.append(f"| {label} | " + " | ".join(fmt(r) for r in evals) + " |")
    lines += ["", "Nguồn: `reports/eval_v1.json`, `eval_v2.json`, `eval_v2_fixed.json`.", "",
              "| ID sai ban đầu | Thiếu nội dung | Cách sửa |", "|---|---|---|",
              "| security-02 | JWT, token, hết hạn, chữ ký | Thêm tài liệu JWT vs API key |",
              "| scaling-03 | Kubernetes HPA, CPU, memory, custom metrics | Thêm tài liệu autoscaling |", "",
              "Chỉ sửa KNOWLEDGE_BASE, đồng bộ develop/production; không sửa golden dataset. "
              "V2 tăng độ chính xác nhưng retrieval làm tăng prompt, token và latency. Cost/câu đúng "
              "thấp hơn v1 trong lần đo này vì có nhiều câu đúng hơn. Đây là keyword-based eval của "
              "mock, chưa phản ánh đầy đủ tính đúng đắn ngữ nghĩa của LLM thật.", "",
              "CI: `.github/workflows/eval.yml` khởi động v2 với lỗi mock tắt để kiểm tra chất lượng "
              "ổn định, yêu cầu accuracy 1.0 và không regression với baseline fixed. Exit code khác 0 "
              "làm job fail; cần bật required status check trên GitHub để chặn merge. Workflow mới "
              "được tạo local, chưa chạy trên GitHub.", "",
              "## 4. Observability stack", "", "### 4.1 Bằng chứng", ""]
    for filename, title in (("grafana-dashboard.png", "Grafana có tải"),
                            ("jaeger-slow-trace.png", "Jaeger trace chậm"),
                            ("jaeger-error-trace.png", "Jaeger trace lỗi"),
                            ("prometheus-alert-firing.png", "Prometheus alerts")):
        exists = (ROOT / "screenshots" / filename).exists()
        lines.append(f"- [{'x' if exists else ' '}] {title}: " +
                     (f"[ảnh](screenshots/{filename})" if exists else "chưa thu thập"))
    lines += ["", "Metrics được Prometheus pull trực tiếp từ agent; Grafana đọc datasource Prometheus. "
              "Nginx chặn `/metrics` từ bên ngoài. Trong Golden Signals, traffic là request rate, "
              "errors là 5xx ratio, latency là histogram percentile, saturation là in-flight requests. "
              "Agent chạy một worker/container để tránh bộ đếm Prometheus tách rời giữa process; "
              "scale bằng số container.", "",
              "Đã sửa Dockerfile mẫu: HOME user là `/app` nhưng packages ở `/home/agent/.local` "
              "khiến uvicorn không import được. Đổi home thành `/home/agent`, rồi rebuild stack.", "",
              "### 4.2 Thí nghiệm lỗi và alerts", "",
              "| Thí nghiệm | Alert quan sát firing | Thời gian tới lần quan sát đầu | Panel liên quan |",
              "|---|---|---|---|"]
    for name, title, panel in (
        ("errors_and_slow", "A+B: error rate 0.2, slow rate 0.3", "Error rate, p95 latency"),
        ("large_model", "C: mock-llm-large", "Cost burn, tokens, latency"),
        ("instance_down", "D: pause một instance", "Instances up, traffic, latency"),
    ):
        report = read(f"alerts_{name}.json")
        firing = report["first_observed_firing_s"] if report else {}
        already_firing = {a["labels"]["alertname"] for a in report["observations"][0]["alerts"]
                          if a["state"] == "firing"} if report and report["observations"] else set()
        alerts = ", ".join(firing) if firing else "chưa có bằng chứng firing"
        timing = "; ".join(f"{key}: " + ("đã firing từ trước" if key in already_firing else f"{value}s")
                           for key, value in firing.items()) or "chưa đo"
        lines.append(f"| {title} | {alerts} | {timing} | {panel} |")
    lines += ["", "A và B được tiêm đồng thời để có ảnh hai alert cùng firing. Thời gian đo tính từ "
              "sau khi recreate agent và đợi DNS, trước khi khởi động load generator; polling mỗi "
              "5 giây, có sai số do polling và thời gian chụp ảnh. Alert vốn đã firing từ thí nghiệm "
              "trước không phải detection mới; đọc chuỗi observations/activeAt trong JSON để phân biệt.", "",
              "E: v1 có thể trả 200 nhanh nhưng sai nội dung. Error/latency alert không đo được điều "
              "đó; cần chạy golden eval trước deploy, canary eval và giám sát chất lượng online. "
              "Nếu có, `reports/eval_production_v1.json` là bằng chứng eval v1 trên stack.", "",
              "### 4.3 Debug bằng trace", ""]
    production_v1 = read("eval_production_v1.json")
    if production_v1:
        lines += [f"Eval v1 trên stack: {production_v1['passed']}/{production_v1['total']} "
                  f"({production_v1['accuracy']:.1%}); quality gate "
                  f"{'PASS' if production_v1['quality_gate']['passed'] else 'FAIL'}. "
                  "Nguồn: reports/eval_production_v1.json.", ""]
    lines += ["Trace được đọc qua [Jaeger Query API v3](https://www.jaegertracing.io/docs/2.23/architecture/apis/). "
              "File `jaeger_*_trace_otlp.json` giữ response OTLP nguyên bản; file `jaeger_*_trace.json` "
              "chỉ chuẩn hóa tên field và đổi đơn vị nanosecond sang microsecond để lập bảng.", ""]
    for kind, title in (("slow", "Trace chậm"), ("error", "Trace lỗi")):
        trace = read(f"jaeger_{kind}_trace.json")
        logs = read(f"jaeger_{kind}_logs.json")
        if not trace:
            lines.append(f"{title}: chưa thu thập.\n")
            continue
        spans = trace["spans"]
        first = min(s["startTime"] for s in spans)
        last = max(s["startTime"] + s["duration"] for s in spans)
        total = (last - first) / 1000
        llm = max((s for s in spans if s["operationName"].startswith("chat ")), key=lambda s: s["duration"])
        ms = llm["duration"] / 1000
        lines += [f"**{title}:** `{trace['traceID']}`; tổng {total:.2f} ms. "
                  f"Span LLM `{llm['operationName']}`: {ms:.2f} ms ({ms / total:.1%} tổng thời gian).", ""]
        if kind == "error":
            exceptions = [log for s in spans for log in s.get("logs", [])
                          if any(f.get("value") == "exception" for f in log.get("fields", []))]
            lines += [f"Có {len(exceptions)} exception event trong các span.", ""]
        if logs:
            lines += ["Dòng log JSON có cùng trace_id:", "", "```json", json.dumps(logs[0], ensure_ascii=False), "```", ""]
        else:
            lines += ["Chưa tìm thấy dòng log cùng trace_id.", ""]
    lines += ["## 5. Scaling benchmark", "", "Locust headless, 100 users, ramp 10 users/giây, 2 phút/mức. "
              "Dòng dưới đây là `/ask` trong CSV; CSV còn có `/health` và Aggregated. "
              "Dùng `compose run --no-deps` để Locust không tự reset số replica về 2; "
              "lưu số container trước mỗi lần chạy trong reports/scale_1_containers.txt và "
              "scale_3_containers.txt. Hai lần đo ban đầu bị reset replica nên đã bị loại và đo lại.", "",
              "| Instance | RPS /ask | p50 ms | p95 ms | p99 ms | Failures / requests |",
              "|---|---:|---:|---:|---:|---:|"]
    for n in (1, 3):
        path = ROOT / f"benchmark-results/scale_{n}_stats.csv"
        if path.exists():
            with path.open(encoding="utf-8-sig", newline="") as f:
                rows = list(csv.DictReader(f))
            row = next(r for r in rows if r.get("Name") == "/ask")
            lines.append(f"| {n} | {float(row['Requests/s']):.2f} | {row['50%']} | {row['95%']} | {row['99%']} | {row['Failure Count']} / {row['Request Count']} |")
        else:
            lines.append(f"| {n} | chưa đo | | | | |")
    lines += ["", "Không kỳ vọng throughput tăng gấp ba: mock chủ yếu async chờ, load generator có "
              "think time 0.5–2 giây, tổng 100 users cố định, và mọi container dùng cùng host. "
              "Chênh lệch nhỏ có thể là nhiễu. Cần profile CPU/queue và lặp có kiểm soát trước khi "
              "kết luận nút thắt hoặc lợi ích scaling thật.", "",
              "## 6. Điều học được và bước tiếp", "",
              "1. Average không mô tả được tail latency; cần percentile cùng error rate.",
              "2. Agent trả 200 chưa chắc trả lời đúng; quality gate bổ sung cho health/metrics.",
              "3. Trace_id nối request, span chậm/lỗi và log; state chung Redis giúp scale an toàn.", "",
              "Khi dùng thực tế: thêm queue depth, dependency availability, token usage chính xác, "
              "budget reservation, cảnh báo chất lượng online và lịch đánh giá có nhãn. Trạng thái "
              "deploy cloud và bằng chứng kiểm tra public URL được ghi riêng trong DEPLOYMENT.md.", ""]
    (ROOT / "BENCHMARK_REPORT.md").write_text("\n".join(lines), encoding="utf-8")
    mission = ROOT / "MISSION_ANSWERS.md"
    text = mission.read_text(encoding="utf-8")
    grader = REPORTS / "production_ready.txt"
    if "<!-- PRODUCTION_CHECKLIST -->" in text and grader.exists():
        output = grader.read_text(encoding="utf-8")
        marker = output.index("  📋 Checklist Deliverable")
        text = text.replace("<!-- PRODUCTION_CHECKLIST -->", "```text\n" + output[marker:].strip() + "\n```")
        mission.write_text(text, encoding="utf-8")
    if "<!-- SECURITY_HTTP_EVIDENCE -->" in text:
        security = read("local_exercises.json")
        samples = [security["part4_missing"], security["part4_authorized"],
                   next(r for r in security["part4_burst"] if r["status"] == 429)]
        snippets = ["Các response HTTP đã thu bằng client, trình bày status/headers/body từ artifact "
                    "(không chứa credential):", ""]
        for response in samples:
            snippets += ["```text", f"Status: {response['status']}"]
            snippets += [f"{key}: {value}" for key, value in response["headers"].items()]
            snippets += ["", json.dumps(response["body"], ensure_ascii=False), "```", ""]
        text = text.replace("<!-- SECURITY_HTTP_EVIDENCE -->", "\n".join(snippets))
        mission.write_text(text, encoding="utf-8")
    print("Rendered report from available artifacts")


if __name__ == "__main__":
    main()
