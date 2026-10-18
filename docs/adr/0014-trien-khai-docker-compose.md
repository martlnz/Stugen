# ADR-0014: Triển khai bằng Docker Compose + reverse proxy Caddy

- **Trạng thái:** Chấp nhận
- **Ngày:** 2026-10-18

## Bối cảnh
Dự án phi thương mại, tài nguyên hạn chế. Cần môi trường dev và prod giống nhau, dễ dựng trên một VPS. ADR-0005 yêu cầu frontend và API cùng domain.

## Các phương án
1. **Docker Compose trên một máy** – đơn giản, đủ cho quy mô nhỏ.
2. **Kubernetes** – quá phức tạp.
3. **Dịch vụ quản lý riêng lẻ** (Vercel + Cloud Run + DB managed) – nhiều nơi cấu hình, khó cùng domain, có thể phát sinh chi phí.

## Quyết định
Chọn **Docker Compose**, với **Caddy** làm reverse proxy (tự động HTTPS qua Let's Encrypt).

### Dịch vụ
| Service | Image / build | Ghi chú |
|---|---|---|
| `proxy` | `caddy:2` | Cổng 80/443 duy nhất mở ra ngoài |
| `web` | `./frontend` (Node 22, standalone) | |
| `api` | `./backend` | Lệnh: `alembic upgrade head && gunicorn ...` |
| `worker` | `./backend` | Lệnh: `celery -A app.worker worker -Q ai,default` |
| `beat` | `./backend` | Lệnh: `celery -A app.worker beat` |
| `postgres` | `postgres:16` | Volume `pgdata` |
| `redis` | `redis:7` | |
| `minio` | `minio/minio` | Volume `miniodata` |

### Định tuyến (Caddyfile)
```
{$DOMAIN} {
    request_body /api/lectures* { max_size 21MB }
    handle /api/* { reverse_proxy api:8000 }
    handle        { reverse_proxy web:3000 }
}
```

### Môi trường
- File `.env` (không commit), có `.env.example` liệt kê đủ biến: DB, Redis, MinIO, Google OAuth, LLM, `DOMAIN`.
- `docker-compose.override.yml` cho dev: hot reload, mount source, `DOMAIN=localhost`.
- Healthcheck: `GET /api/health` kiểm tra DB và Redis.

### Sao lưu
Cron hằng ngày `pg_dump` + `mc mirror` MinIO sang thư mục sao lưu; giữ 7 bản.

## Hệ quả
- **Tích cực:** Một lệnh `docker compose up` cho toàn hệ thống; dev và prod giống nhau; cùng domain giải quyết cookie và CORS; HTTPS miễn phí.
- **Tiêu cực:** Một máy chủ duy nhất (không chịu lỗi phần cứng); mở rộng theo chiều ngang hạn chế — đủ với dự án phi thương mại.
