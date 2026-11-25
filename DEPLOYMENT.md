# Deployment Information — Day 14

## Public URL và trạng thái

- **Public URL:** [https://k5-day14-agent-j5ql.onrender.com](https://k5-day14-agent-j5ql.onrender.com)
- **Platform:** Render; web service Docker và Key Value (Redis) đều **Free**, region Singapore.
- **Trạng thái:** deployment `dep-dc3b3vl9fdbs738cd3og` là `live`.
- **Code đã deploy:** commit `c85378e40493ef58d9422069e6d19e2f9f30aaa4` từ branch `main`, root directory `06-lab-complete/`.
- **Dashboard:** [Render service](https://dashboard.render.com/web/srv-dc3b3vd9fdbs738cd310).
- **Đã kiểm tra:** 25/11/2026 17:02:57 GMT+7.

## Kiểm tra public thực tế

| Request | API key | HTTP thực tế | Kết quả |
|---|---|---:|---|
| `GET /health` | Không cần | 200 | PASS |
| `GET /ready` | Không cần | 200 | PASS, Redis kết nối được |
| `POST /ask` | Không có | 401 | PASS |
| `POST /ask` | Đúng key | 200 | PASS, mock agent trả lời |

Output từng response đã lưu trong [`reports/public_deployment_checks.json`](reports/public_deployment_checks.json). Credential không có trong report.

Script chấm nguyên bản đã chạy đầy đủ trên Linux/Python 3.11, có Docker, kèm `--public-url`: **PASS 12/12, 44/44 checks**. Output: [`reports/production_ready.txt`](reports/production_ready.txt).

## Cấu hình đã đặt

| Biến | Cách cấu hình |
|---|---|
| `PORT` | Render cấp; Docker CMD đọc theo env |
| `ENVIRONMENT` | `production` |
| `AGENT_API_KEY` | Key ngẫu nhiên, đặt trong environment của Render; không commit |
| `REDIS_URL` | URL nội bộ của Render Key Value; không public cổng Redis |
| `RATE_LIMIT_PER_MINUTE` | `10` |
| `DAILY_BUDGET_USD` | `1` |
| `MONTHLY_BUDGET_USD` | `10` |

Service `srv-dc3b3vd9fdbs738cd310` dùng Redis `red-dc3b2jm7bikc73cm9oig`. Redis có `ipAllowList: []`, `maxmemoryPolicy: noeviction`, `persistenceMode: off`. Metadata không chứa credential: [`reports/render_deployment.json`](reports/render_deployment.json), [`reports/render_deployments.json`](reports/render_deployments.json).

API key có thể xem trong Render Dashboard → Environment. Bản dùng để tự kiểm được giữ ở file local bị Git ignore `.lab-tools/render-deployment.private.json`; không gửi hoặc commit file này.

## Lệnh tái kiểm tra (Bash/WSL)

Đặt `AGENT_API_KEY` riêng trong terminal trước khi chạy; các lệnh chỉ in HTTP status.

```bash
BASE=https://k5-day14-agent-j5ql.onrender.com
curl -sS -o /dev/null -w '%{http_code}\n' "$BASE/health"
curl -sS -o /dev/null -w '%{http_code}\n' "$BASE/ready"
curl -sS -o /dev/null -w '%{http_code}\n' -X POST "$BASE/ask" \
  -H 'Content-Type: application/json' -d '{"question":"Hello"}'
curl -sS -o /dev/null -w '%{http_code}\n' -X POST "$BASE/ask" \
  -H 'Content-Type: application/json' -H "X-API-Key: $AGENT_API_KEY" \
  -d '{"question":"Hello"}'
```

Kỳ vọng lần lượt: `200`, `200`, `401`, `200`.

## Ảnh minh chứng

- [Dashboard Render: Free, Live, commit và URL](screenshots/dashboard.png).
- [Service running: GET /health trả 200](screenshots/running.png).
- [API test: POST /ask thiếu key trả 401](screenshots/test.png).

Đây là ảnh chụp thật của dashboard và Swagger trên URL public. Trường hợp key đúng trả 200 được lưu trong JSON để ảnh không lộ key.

## Railway đã thử trước đó

Railway tạo được project nhưng chặn deploy với thông báo `Suspicious activity: Your workspace has been restricted`; Redis deployment FAILED, agent chưa được tạo. Không nâng cấp trả phí. Học viên chọn chuyển sang Render free. Bằng chứng: [`reports/railway_deployment_status.json`](reports/railway_deployment_status.json).

## Giới hạn gói free

Web service có thể ngủ sau thời gian không có traffic; request tiếp theo có cold start. Redis free không có persistence qua restart của chính Redis. State vẫn dùng chung và tồn tại qua restart agent khi Redis không restart. Xem [giới hạn Render Free](https://render.com/docs/free).

Auto-deploy tắt để giữ deployment đã kiểm tra. Các commit bổ sung báo cáo sau commit deploy không thay đổi source agent đang chạy; nếu sửa app, cần manual deploy rồi kiểm tra lại.
