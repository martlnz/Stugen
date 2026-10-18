# ADR-0002: Kiến trúc tổng thể – Frontend, Backend API, AI Worker

- **Trạng thái:** Chấp nhận
- **Ngày:** 2026-10-18

## Bối cảnh
PRD yêu cầu: frontend tự chọn, backend và AI service dùng Python. Việc sinh tóm tắt/slide/quiz cho một PDF mất từ vài chục giây tới vài phút, không thể xử lý trong vòng đời một HTTP request.

## Yếu tố quyết định
- Request HTTP phải phản hồi nhanh, không bị timeout khi xử lý PDF dài.
- Xử lý AI tốn tài nguyên, cần tách để không ảnh hưởng API.
- Dự án nhỏ, ít người: tránh độ phức tạp của microservices thực thụ.
- Backend và AI cùng Python nên có thể chia sẻ code (model, schema).

## Các phương án
1. **Monolith đồng bộ** – FastAPI xử lý PDF ngay trong request. Đơn giản nhưng timeout, chặn worker HTTP, không chịu được PDF dài.
2. **Microservices** – AI service là service HTTP riêng, backend gọi qua REST. Tách biệt tốt nhưng phải quản lý thêm API nội bộ, retry, timeout giữa service.
3. **Backend API + Worker qua hàng đợi, chung codebase Python** – API nhận request và đẩy job; worker cùng codebase lấy job và xử lý.

## Quyết định
Chọn **phương án 3**. Hệ thống gồm:

| Thành phần | Vai trò |
|---|---|
| `web` (Next.js) | Giao diện người dùng |
| `api` (FastAPI) | Xác thực, CRUD, nhận upload, đẩy job, chấm quiz |
| `worker` (Celery) | Trích xuất PDF, gọi LLM, sinh PPTX |
| `postgres` | Dữ liệu có cấu trúc |
| `redis` | Broker hàng đợi |
| `minio` | Lưu PDF và PPTX |
| `proxy` (Caddy) | Gom frontend và API về cùng domain |

`api` và `worker` là hai **tiến trình** khác nhau của **cùng một package Python** (`backend/`), dùng chung model SQLAlchemy, schema Pydantic và cấu hình. Chúng chỉ giao tiếp qua PostgreSQL (trạng thái, kết quả) và Redis (job).

## Cấu trúc repository
```
.
├── frontend/                 # Next.js
├── backend/
│   ├── app/
│   │   ├── api/              # FastAPI routers
│   │   ├── core/             # config, security, deps
│   │   ├── db/               # models, session
│   │   ├── schemas/          # Pydantic schemas (API + đầu ra LLM)
│   │   ├── services/         # logic nghiệp vụ dùng chung
│   │   ├── ai/               # pdf extraction, llm client, prompts, generators
│   │   ├── worker/           # Celery app + tasks
│   │   └── main.py
│   ├── alembic/
│   └── pyproject.toml
├── docs/
│   ├── PRD.md
│   └── adr/
├── docker-compose.yml
└── Caddyfile
```

## Hệ quả
- **Tích cực:** API luôn phản hồi nhanh; có thể tăng số worker độc lập; không cần API nội bộ; một ngôn ngữ cho toàn bộ phía server.
- **Tiêu cực:** Thêm Redis và tiến trình worker phải vận hành; image Docker của API kéo theo cả thư viện AI (chấp nhận được, hoặc tách dependency group nếu image quá nặng).
- Nếu sau này cần tách AI thành service độc lập, ranh giới đã rõ ở thư mục `app/ai/`.
