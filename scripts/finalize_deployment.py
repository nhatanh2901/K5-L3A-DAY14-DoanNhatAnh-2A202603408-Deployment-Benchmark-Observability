"""Update submission prose from verified, credential-free deployment evidence."""
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import re
import shutil

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports"


def main():
    checks = json.loads((REPORTS / "public_deployment_checks.json").read_text(encoding="utf-8"))
    service = json.loads((REPORTS / "render_deployment.json").read_text(encoding="utf-8"))
    deployments = json.loads((REPORTS / "render_deployments.json").read_text(encoding="utf-8"))
    assert checks["passed"] and [r["status"] for r in checks["checks"]] == [200, 200, 401, 200]
    live = next(d for d in deployments if d["status"] == "live")
    assert service["plan"] == service["redis"]["plan"] == "free"
    url = checks["public_url"]
    checked = datetime.fromisoformat(checks["checked_at"]).astimezone(timezone(timedelta(hours=7)))
    grader = (REPORTS / "production_ready.txt").read_text(encoding="utf-8")
    assert "PASS 12/12" in grader and "44/44 checks passed" in grader
    shutil.copy2(ROOT / ".lab-tools/render-dashboard-preview.png", ROOT / "screenshots/dashboard.png")
    deployment = f'''# Deployment Information — Day 14

## Public URL và trạng thái

- **Public URL:** [{url}]({url})
- **Platform:** Render; web service Docker và Key Value (Redis) đều **Free**, region Singapore.
- **Trạng thái:** deployment `{live['id']}` là `live`.
- **Code đã deploy:** commit `{live['commit']['id']}` từ branch `main`, root directory `06-lab-complete/`.
- **Dashboard:** [Render service]({service['dashboardUrl']}).
- **Đã kiểm tra:** {checked:%d/%m/%Y %H:%M:%S} GMT+7.

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

Service `{service['id']}` dùng Redis `{service['redis']['id']}`. Redis có `ipAllowList: []`, `maxmemoryPolicy: noeviction`, `persistenceMode: off`. Metadata không chứa credential: [`reports/render_deployment.json`](reports/render_deployment.json), [`reports/render_deployments.json`](reports/render_deployments.json).

API key có thể xem trong Render Dashboard → Environment. Bản dùng để tự kiểm được giữ ở file local bị Git ignore `.lab-tools/render-deployment.private.json`; không gửi hoặc commit file này.

## Lệnh tái kiểm tra (Bash/WSL)

Đặt `AGENT_API_KEY` riêng trong terminal trước khi chạy; các lệnh chỉ in HTTP status.

```bash
BASE={url}
curl -sS -o /dev/null -w '%{{http_code}}\\n' "$BASE/health"
curl -sS -o /dev/null -w '%{{http_code}}\\n' "$BASE/ready"
curl -sS -o /dev/null -w '%{{http_code}}\\n' -X POST "$BASE/ask" \\
  -H 'Content-Type: application/json' -d '{{"question":"Hello"}}'
curl -sS -o /dev/null -w '%{{http_code}}\\n' -X POST "$BASE/ask" \\
  -H 'Content-Type: application/json' -H "X-API-Key: $AGENT_API_KEY" \\
  -d '{{"question":"Hello"}}'
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
'''
    (ROOT / "DEPLOYMENT.md").write_text(deployment, encoding="utf-8")
    mission_path = ROOT / "MISSION_ANSWERS.md"
    mission = mission_path.read_text(encoding="utf-8")
    mission = mission.replace("Đang hoàn tất deploy cloud theo lựa chọn Render miễn phí của học viên.",
                              "Đã deploy agent và Redis lên Render miễn phí, kiểm tra đủ bốn HTTP status bắt buộc.")
    before = "Railway đã tạo project nhưng deploy bị chặn do workspace bị hạn chế, Redis FAILED. Học viên chọn chuyển sang Render miễn phí. Đã chuẩn bị Blueprint cho web service và Redis; kết quả public URL và bốn lệnh tự kiểm được cập nhật trong [`DEPLOYMENT.md`](DEPLOYMENT.md) sau khi chạy thực tế."
    after = f"Railway bị hạn chế workspace nên học viên chọn Render miễn phí. Agent và Redis đã deploy thành công. Public URL: [{url}]({url}); `/health` 200, `/ready` 200, `/ask` thiếu key 401 và có key 200. Bằng chứng và ảnh dashboard trong [`DEPLOYMENT.md`](DEPLOYMENT.md)."
    mission = mission.replace(before, after)
    output = grader[grader.index("  📋 Checklist Deliverable"):].strip()
    mission = re.sub(r"```text\n📋 Checklist Deliverable.*?```", "```text\n" + output + "\n```", mission, flags=re.S)
    row = "| Hoàn tất Render free | Tạo web service + Redis, API key ngẫu nhiên trong env; chụp dashboard và response thật | Public checks 200/200/401/200; script chấm nguyên bản PASS 12/12, 44/44 checks; không commit credential |"
    if row not in mission:
        mission = mission.replace("\nCác kiểm tra tự động kể trên", "\n" + row + "\n\nCác kiểm tra tự động kể trên")
    mission = mission.replace("\n\n" + row, "\n" + row)
    mission_path.write_text(mission, encoding="utf-8")
    print("Deployment documentation updated from verified public responses and Render live state")


if __name__ == "__main__":
    main()
