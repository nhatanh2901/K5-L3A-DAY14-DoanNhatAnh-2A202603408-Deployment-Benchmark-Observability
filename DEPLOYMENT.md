# Deployment Information — Day 14

## Trạng thái

Đang triển khai lên Render miễn phí theo lựa chọn của học viên. Chưa có public URL hoạt động để xác nhận. `PASS 12/12` hiện chứng minh agent local và cấu hình deploy hợp lệ.

Railway đã tạo project `k5-day14-agent` nhưng chặn deploy với thông báo `Suspicious activity: Your workspace has been restricted`. Redis deployment FAILED, service agent chưa tạo được. Không nâng cấp trả phí. Bằng chứng: [`reports/railway_deployment_status.json`](reports/railway_deployment_status.json).

## Code và nền tảng đã chuẩn bị

- Deploy thư mục `06-lab-complete/`, dùng `Dockerfile` và `railway.toml` trong thư mục này.
- Blueprint Render: `06-lab-complete/render.yaml`, gồm web service Docker và Key Value (Redis), cùng region Singapore, đều `plan: free`.
- `REDIS_URL` tham chiếu connection string nội bộ của Key Value; không public cổng Redis.
- Đặt `AGENT_API_KEY` bằng secret của nền tảng. Không đưa giá trị thật vào repo.

## Environment variables

`PORT` do nền tảng cấp; `ENVIRONMENT=production`; `AGENT_API_KEY`; `REDIS_URL`; `RATE_LIMIT_PER_MINUTE=10`; `DAILY_BUDGET_USD=1`; `MONTHLY_BUDGET_USD=10`.

## Kiểm tra sau khi deploy (Bash/WSL)

Đặt `BASE` là URL được nền tảng cấp và `AGENT_API_KEY` trong terminal riêng. Những lệnh dưới đây chỉ in HTTP status, không in secret.

```bash
curl -sS -o /dev/null -w '%{http_code}\n' "$BASE/health"
curl -sS -o /dev/null -w '%{http_code}\n' "$BASE/ready"
curl -sS -o /dev/null -w '%{http_code}\n' -X POST "$BASE/ask" \
  -H 'Content-Type: application/json' -d '{"question":"Hello"}'
curl -sS -o /dev/null -w '%{http_code}\n' -X POST "$BASE/ask" \
  -H 'Content-Type: application/json' -H "X-API-Key: $AGENT_API_KEY" \
  -d '{"question":"Hello"}'
```

Kỳ vọng theo thứ tự: `200`, `200`, `401`, `200`. Các lệnh cloud này chưa được chạy.

## Phần còn phải bổ sung khi làm deploy

- Public URL thật và tên nền tảng đã dùng.
- Output bốn lệnh trên và `check_production_ready.py --public-url "$BASE"`.
- `screenshots/dashboard.png`, `screenshots/running.png`, `screenshots/test.png`, đã che secrets.

## Giới hạn gói free

Web service có thể ngủ khi không có traffic; lần gọi sau có cold start. Key Value free không có persistence qua restart của chính Redis. State vẫn dùng chung và tồn tại qua restart agent nếu Redis không bị restart. Xem [Render Free](https://render.com/docs/free).
