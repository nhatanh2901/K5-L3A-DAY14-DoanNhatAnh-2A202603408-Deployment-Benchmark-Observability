# Benchmark & Observability Report — Day 14

**Họ tên:** DoanNhatAnh

**Ngày chạy:** 25/11/2026 (GMT+7)

Docker engine 29.9.3, 12 CPU, 7.58 GiB RAM được cấp cho Docker; nguồn: reports/environment.json.

**Môi trường:** Windows, Docker Desktop Linux, Python 3.11 trong container; mock LLM. Host Python 3.13 chỉ điều phối Docker và lưu evidence, không chạy script chấm SIGTERM.

Mọi số dưới đây đọc từ JSON/CSV trong repo. Các lần chạy là một lần đo, có ngẫu nhiên; không chứng minh hiệu năng của LLM/provider thật. Load test local ban đầu chạy cùng lúc với một số kiểm tra khác nên có thể bị ảnh hưởng bởi tranh chấp CPU/I/O.

## 1. SLO của agent

| SLI | SLO | Lý do |
|---|---|---|
| p95 `/ask` local | ≤ 500 ms | Ngưỡng mặc định của load_test.py |
| Error rate local | ≤ 2% | Ngưỡng mặc định của load_test.py |
| Accuracy eval sau sửa KB | 100%, không regression | Quality gate theo CP7 |

Alert rules production là ngưỡng khác: error rate >5% trong 1 phút; p95 >1 giây trong 2 phút; instance down 30 giây; cost burn >2 USD/giờ trong 2 phút.

## 2. Benchmark hiệu năng

### 2.1 Concurrency vs latency

300 request mỗi mức; agent v2, default mock latency/jitter, slow rate 0.03 và error rate 0.01.

| Concurrency | RPS | p50 ms | p95 ms | p99 ms | Error rate | SLO |
|---|---:|---:|---:|---:|---:|---|
| 1 | 4.3 | 194.6 | 225.6 | 1689.2 | 0.67% | PASS |
| 10 | 35.88 | 203.5 | 238.3 | 1706.4 | 2.00% | PASS |
| 50 | 105.36 | 263.7 | 333.3 | 1734.8 | 0.67% | PASS |
| 100 | 63.63 | 469.1 | 3494.5 | 3898.1 | 0.67% | FAIL |

Nguồn: `reports/load_v2_c*.json`. Latency trong script chỉ tính các response 200; error rate tính toàn bộ request. Vì vậy cần đọc đồng thời cả hai chỉ số.

RPS không tăng tuyến tính: concurrency 100 có RPS thấp hơn 50 và p95 tăng mạnh. Đây là quan sát trên môi trường đo này, có thể do tải đồng thời và scheduling; chưa đủ dữ liệu để khẳng định nút thắt CPU hay network. Không đổi số để ép SLO PASS.

### 2.2 Tail latency

Cùng 300 request và concurrency 20, restart agent mỗi mức slow rate.

| MOCK_SLOW_RATE | avg ms | p95 ms | p99 ms |
|---|---:|---:|---:|
| 0 | 220.3 | 259.5 | 269.7 |
| 0.03 | 230.6 | 244.7 | 1677.9 |
| 0.1 | 327.2 | 1707.3 | 1737.7 |

Nguồn: `reports/load_v2_slow_*.json`. p99 nhạy với đuôi chậm ở mức 3%; khi khoảng 10% request chậm, p95 cũng tăng rõ. Average pha loãng trải nghiệm xấu của nhóm nhỏ người dùng; nên đặt SLO theo percentile và theo dõi error riêng.

## 3. Benchmark chất lượng

| Chỉ số | v1 | v2 ban đầu | v2 sửa KB |
|---|---:|---:|---:|
| Accuracy | 4.3% (1/23) | 91.3% (21/23) | 100.0% (23/23) |
| Avg tokens/câu | 57.4 | 109.0 | 117.4 |
| Tổng cost USD | 0.000409 | 0.00076 | 0.000823 |
| Cost/câu đúng USD | 0.00040875 | 3.619e-05 | 3.579e-05 |
| p95 ms | 191.2 | 219.1 | 220.7 |
| Quality gate | FAIL | PASS | PASS |

Nguồn: `reports/eval_v1.json`, `eval_v2.json`, `eval_v2_fixed.json`.

| ID sai ban đầu | Thiếu nội dung | Cách sửa |
|---|---|---|
| security-02 | JWT, token, hết hạn, chữ ký | Thêm tài liệu JWT vs API key |
| scaling-03 | Kubernetes HPA, CPU, memory, custom metrics | Thêm tài liệu autoscaling |

Chỉ sửa KNOWLEDGE_BASE, đồng bộ develop/production; không sửa golden dataset. V2 tăng độ chính xác nhưng retrieval làm tăng prompt, token và latency. Cost/câu đúng thấp hơn v1 trong lần đo này vì có nhiều câu đúng hơn. Đây là keyword-based eval của mock, chưa phản ánh đầy đủ tính đúng đắn ngữ nghĩa của LLM thật.

CI: `.github/workflows/eval.yml` khởi động v2 với lỗi mock tắt để kiểm tra chất lượng ổn định, yêu cầu accuracy 1.0 và không regression với baseline fixed. Exit code khác 0 làm job fail; cần bật required status check trên GitHub để chặn merge. Workflow mới được tạo local, chưa chạy trên GitHub.

## 4. Observability stack

### 4.1 Bằng chứng

- [x] Grafana có tải: [ảnh](screenshots/grafana-dashboard.png)
- [x] Jaeger trace chậm: [ảnh](screenshots/jaeger-slow-trace.png)
- [x] Jaeger trace lỗi: [ảnh](screenshots/jaeger-error-trace.png)
- [x] Prometheus alerts: [ảnh](screenshots/prometheus-alert-firing.png)

Metrics được Prometheus pull trực tiếp từ agent; Grafana đọc datasource Prometheus. Nginx chặn `/metrics` từ bên ngoài. Trong Golden Signals, traffic là request rate, errors là 5xx ratio, latency là histogram percentile, saturation là in-flight requests. Agent chạy một worker/container để tránh bộ đếm Prometheus tách rời giữa process; scale bằng số container.

Đã sửa Dockerfile mẫu: HOME user là `/app` nhưng packages ở `/home/agent/.local` khiến uvicorn không import được. Đổi home thành `/home/agent`, rồi rebuild stack.

### 4.2 Thí nghiệm lỗi và alerts

| Thí nghiệm | Alert quan sát firing | Thời gian tới lần quan sát đầu | Panel liên quan |
|---|---|---|---|
| A+B: error rate 0.2, slow rate 0.3 | LLMCostBurnRateHigh, AgentHighErrorRate, AgentHighLatencyP95 | LLMCostBurnRateHigh: đã firing từ trước; AgentHighErrorRate: 80.41s; AgentHighLatencyP95: 134.29s | Error rate, p95 latency |
| C: mock-llm-large | LLMCostBurnRateHigh | LLMCostBurnRateHigh: đã firing từ trước | Cost burn, tokens, latency |
| D: pause một instance | LLMCostBurnRateHigh, AgentInstanceDown | LLMCostBurnRateHigh: đã firing từ trước; AgentInstanceDown: 45.29s | Instances up, traffic, latency |

A và B được tiêm đồng thời để có ảnh hai alert cùng firing. Thời gian đo tính từ sau khi recreate agent và đợi DNS, trước khi khởi động load generator; polling mỗi 5 giây, có sai số do polling và thời gian chụp ảnh. Alert vốn đã firing từ thí nghiệm trước không phải detection mới; đọc chuỗi observations/activeAt trong JSON để phân biệt.

E: v1 có thể trả 200 nhanh nhưng sai nội dung. Error/latency alert không đo được điều đó; cần chạy golden eval trước deploy, canary eval và giám sát chất lượng online. Nếu có, `reports/eval_production_v1.json` là bằng chứng eval v1 trên stack.

### 4.3 Debug bằng trace

Eval v1 trên stack: 1/23 (4.3%); quality gate FAIL. Nguồn: reports/eval_production_v1.json.

Trace được đọc qua [Jaeger Query API v3](https://www.jaegertracing.io/docs/2.23/architecture/apis/). File `jaeger_*_trace_otlp.json` giữ response OTLP nguyên bản; file `jaeger_*_trace.json` chỉ chuẩn hóa tên field và đổi đơn vị nanosecond sang microsecond để lập bảng.

**Trace chậm:** `802c8b9155e19b4a8ef13aa626ee0cad`; tổng 2020.22 ms. Span LLM `chat mock-llm-large`: 1996.08 ms (98.8% tổng thời gian).

Dòng log JSON có cùng trace_id:

```json
{"ts": "2026-11-25T08:55:06.828943+00:00", "level": "INFO", "service": "observable-agent", "instance": "672032fe7a0f", "event": "llm_call", "trace_id": "802c8b9155e19b4a8ef13aa626ee0cad", "span_id": "d2ac8847f93cb1ba", "request_id": "326342972a83", "model": "mock-llm-large", "agent_version": "v2", "input_tokens": 92, "output_tokens": 55, "cost_usd": 0.00078, "llm_ms": 1994.6}
```

**Trace lỗi:** `78185894fddda4266168d1f13e934df5`; tổng 257.01 ms. Span LLM `chat mock-llm-large`: 230.85 ms (89.8% tổng thời gian).

Có 2 exception event trong các span.

Dòng log JSON có cùng trace_id:

```json
{"ts": "2026-11-25T08:56:31.004269+00:00", "level": "INFO", "service": "observable-agent", "instance": "672032fe7a0f", "event": "llm_error", "trace_id": "78185894fddda4266168d1f13e934df5", "span_id": "7964fe5b124598c1", "request_id": "919d02839b08", "error": "Upstream LLM error: 503 Service Unavailable (mock)"}
```

## 5. Scaling benchmark

Locust headless, 100 users, ramp 10 users/giây, 2 phút/mức. Dòng dưới đây là `/ask` trong CSV; CSV còn có `/health` và Aggregated. Dùng `compose run --no-deps` để Locust không tự reset số replica về 2; lưu số container trước mỗi lần chạy trong reports/scale_1_containers.txt và scale_3_containers.txt. Hai lần đo ban đầu bị reset replica nên đã bị loại và đo lại.

| Instance | RPS /ask | p50 ms | p95 ms | p99 ms | Failures / requests |
|---|---:|---:|---:|---:|---:|
| 1 | 58.97 | 200 | 270 | 1700 | 65 / 7060 |
| 3 | 59.67 | 190 | 230 | 1700 | 75 / 7147 |

Không kỳ vọng throughput tăng gấp ba: mock chủ yếu async chờ, load generator có think time 0.5–2 giây, tổng 100 users cố định, và mọi container dùng cùng host. Chênh lệch nhỏ có thể là nhiễu. Cần profile CPU/queue và lặp có kiểm soát trước khi kết luận nút thắt hoặc lợi ích scaling thật.

## 6. Điều học được và bước tiếp

1. Average không mô tả được tail latency; cần percentile cùng error rate.
2. Agent trả 200 chưa chắc trả lời đúng; quality gate bổ sung cho health/metrics.
3. Trace_id nối request, span chậm/lỗi và log; state chung Redis giúp scale an toàn.

Khi dùng thực tế: thêm queue depth, dependency availability, token usage chính xác, budget reservation, cảnh báo chất lượng online và lịch đánh giá có nhãn. Trạng thái deploy cloud và bằng chứng kiểm tra public URL được ghi riêng trong DEPLOYMENT.md.
