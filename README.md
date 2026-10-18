<h1 align="center">Stugen</h1>

<p align="center">
  <b>Biến giáo trình PDF thành tóm tắt, slide và quiz ôn tập — bằng AI.</b>
</p>

<p align="center">
  <img alt="Status" src="https://img.shields.io/badge/version-0.1.0-blue">
  <img alt="Next.js" src="https://img.shields.io/badge/Next.js-TypeScript-black?logo=nextdotjs">
  <img alt="FastAPI" src="https://img.shields.io/badge/FastAPI-Python%203.12-009688?logo=fastapi&logoColor=white">
  <img alt="PostgreSQL" src="https://img.shields.io/badge/PostgreSQL-16-336791?logo=postgresql&logoColor=white">
  <img alt="Docker" src="https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker&logoColor=white">
  <img alt="License" src="https://img.shields.io/badge/license-AGPL--3.0-green">
</p>

---

**Stugen** là website phi thương mại giúp sinh viên và người tự học ôn tập nhanh hơn. Người dùng đăng nhập bằng tài khoản Google, tải lên giáo trình PDF và nhận về:

- 📝 **Tóm tắt** theo chương — ý chính, thuật ngữ kèm định nghĩa, số trang tham chiếu tới PDF gốc, hỗ trợ công thức toán.
- 📊 **Slide** trình chiếu — xem trực tuyến hoặc tải về dạng **PPTX**.
- ✅ **Quiz** trắc nghiệm 4 lựa chọn (10 / 20 / 30 câu) — chấm điểm, giải thích, lưu lịch sử làm bài.

Mọi bài giảng được lưu trong **thư viện cá nhân** theo tài khoản để xem lại sau.

> [!NOTE]
> Bản **v0.1.0** chạy được trọn luồng đăng nhập Google → tải PDF → tóm tắt, slide, quiz → thư viện trên máy local. Hạn chế đã biết: [docs/known-issues.md](docs/known-issues.md).

## Kiến trúc

```mermaid
flowchart LR
    U([Người dùng]) --> P[Caddy<br/>reverse proxy]
    P -->|/| W[web<br/>Next.js]
    P -->|/api| A[api<br/>FastAPI]
    A -->|job| R[(Redis)]
    R --> K[worker<br/>Celery]
    A --> DB[(PostgreSQL)]
    K --> DB
    A --> S[(MinIO<br/>PDF, PPTX)]
    K --> S
    K --> L[LLM API<br/>/ Ollama]
```

- **Frontend và API cùng domain** qua Caddy; xác thực bằng cookie phiên `HttpOnly` do backend cấp.
- **Tác vụ chậm** (trích xuất PDF, gọi LLM, xuất PPTX) chạy trong Celery worker; frontend theo dõi tiến trình bằng polling.
- **LLM xử lý theo chương** (map–reduce), đầu ra JSON được kiểm tra bằng Pydantic trước khi lưu.

Chi tiết: [ADR-0002](docs/adr/0002-kien-truc-tong-the.md).

## Công nghệ

| Thành phần | Công nghệ |
|---|---|
| Frontend | Next.js (App Router), TypeScript, Tailwind CSS, shadcn/ui, TanStack Query, Reveal.js, react-pdf, KaTeX |
| Backend API | Python 3.12, FastAPI, SQLAlchemy 2.0, Alembic, Authlib (Google OAuth) |
| AI Worker | Celery, PyMuPDF, python-pptx, Pydantic, LLM API (mặc định DeepSeek; Anthropic / OpenAI / Ollama) |
| Hạ tầng | PostgreSQL 16, Redis 7, MinIO, Caddy, Docker Compose |

## Tài liệu

| Tài liệu | Nội dung |
|---|---|
| [PRD](docs/product/PRD.md) | Sản phẩm làm gì, phạm vi, chức năng, tiêu chí hoàn thành |
| [ADR](docs/adr/README.md) | 16 quyết định kiến trúc và lý do lựa chọn |
| [Mô hình dữ liệu](docs/design/data-model.md) | ERD, chi tiết bảng, cấu trúc JSONB, vòng đời trạng thái, DDL |
| [Tài liệu API](docs/design/api.md) | Hợp đồng REST giữa frontend và backend, mã lỗi |
| [Tiến độ](docs/progress.md) | Đã làm gì, việc tiếp theo, vấn đề mở – đọc đầu tiên khi tiếp tục dự án |
| [Hạn chế đã biết](docs/known-issues.md) | Kết quả chạy thử v0.1.0 và các hạn chế hiện tại |
| [Kế hoạch 1 ngày](docs/plans/plan-1-ngay.md) | Lịch phát triển MVP theo từng khối |
| [CLAUDE.md](CLAUDE.md) | Quy tắc code và quy trình khi làm việc với Claude Code |

**Thứ tự đọc đề xuất:** PRD → ADR → Mô hình dữ liệu → API.

## Cấu trúc repository

```
Stugen/
├── README.md
├── CLAUDE.md                  # Hướng dẫn cho Claude Code
├── LICENSE                    # AGPL-3.0
├── .env.example               # Mẫu biến môi trường
├── docker-compose.yml         # proxy, web, api, worker, postgres, redis, minio
├── docker-compose.override.yml# Dev: mount source backend, hot reload API
├── Caddyfile                  # Reverse proxy: / → web, /api → api
├── justfile                   # Lệnh phát triển (just)
├── frontend/                  # Next.js (App Router) + TypeScript + shadcn/ui
├── backend/
│   ├── app/                   # api/, core/, db/, schemas/, services/, ai/, worker/
│   ├── alembic/               # Migration
│   ├── scripts/dev_session.py # Tạo phiên đăng nhập dev (chỉ local)
│   └── tests/                 # pytest + PDF fixture
├── scripts/
│   └── make_sample_pdfs.py    # Sinh PDF mẫu để thử pipeline
└── docs/
    ├── progress.md            # Tiến độ, việc tiếp theo
    ├── known-issues.md        # Hạn chế đã biết của bản hiện tại
    ├── product/
    │   └── PRD.md             # Yêu cầu sản phẩm
    ├── design/
    │   ├── data-model.md      # Mô hình dữ liệu
    │   └── api.md             # Tài liệu REST API
    ├── adr/                   # Architecture Decision Records
    │   ├── README.md          # Mục lục ADR
    │   ├── template.md        # Mẫu ADR mới
    │   └── 0001 … 0016-*.md
    └── plans/
        └── plan-1-ngay.md     # Kế hoạch phát triển
```

## Chạy dự án

**Yêu cầu:** Docker Desktop, Node 22+ (chỉ để lint/sinh kiểu TS), [`just`](https://github.com/casey/just) (`winget install Casey.Just`), API key LLM (mặc định [DeepSeek](https://platform.deepseek.com)), OAuth Client trên Google Cloud Console (loại *Web application*) với redirect URI `http://localhost/api/auth/google/callback` và email của bạn trong *Test users*.

```bash
cp .env.example .env      # điền Google OAuth, LLM API key, mật khẩu DB/MinIO, SESSION_SECRET
just up                   # docker compose up -d --build (migration tự chạy khi api khởi động)
```

- Ứng dụng: <http://localhost> (mở bằng Chrome/Edge/Firefox; cookie phiên có cờ `Secure`, trình duyệt chấp nhận trên `localhost`)
- Tài liệu API (OpenAPI): <http://localhost/api/docs>
- MinIO console: <http://localhost:9001>

**Lệnh thường dùng**

| Lệnh | Việc |
|---|---|
| `just logs` | Xem log `api` và `worker` |
| `just test` | pytest backend trong container `api` (DB test riêng, LLM giả) |
| `just lint` | ruff (backend) + eslint, tsc (frontend; cần `cd frontend && npm ci` một lần) |
| `just fmt` | Định dạng code |
| `just migrate` / `just revision "mô tả"` | Alembic |
| `just gen-api` | Sinh `frontend/src/lib/api-types.ts` từ OpenAPI (khi stack đang chạy) |
| `just session` | Tạo phiên đăng nhập dev (in token cho cookie `sid`) để thử API bằng curl mà không qua Google |

Không có API key LLM? Đặt `LLM_PROVIDER=fake` trong `.env` để chạy pipeline với nội dung giả.

## Quy ước

- Tài liệu viết bằng Markdown, sơ đồ bằng Mermaid.
- Thay đổi kiến trúc → thêm ADR mới theo [`docs/adr/template.md`](docs/adr/template.md); không sửa ADR đã chấp nhận.
- Thay đổi lược đồ hoặc API → cập nhật `docs/design/data-model.md` / `docs/design/api.md` trong cùng pull request với code.
- Commit theo [Conventional Commits](https://www.conventionalcommits.org/): `feat(api): ...`, `fix(worker): ...`, `docs: ...`.

## Phiên bản tài liệu

| Tài liệu | Phiên bản | Ngày |
|---|---|---|
| PRD | 2.3 | 19/10/2026 |
| ADR | 0001–0016 | 19/10/2026 |
| Mô hình dữ liệu | 1.2 | 19/10/2026 |
| Tài liệu API | 1.1 | 19/10/2026 |

## Giấy phép

[GNU AGPL-3.0](LICENSE). Chọn AGPL vì PyMuPDF dùng giấy phép AGPL (xem [ADR-0009](docs/adr/0009-trich-xuat-pdf-pymupdf.md), [ADR-0016](docs/adr/0016-cong-cu-ten-tai-nguyen-deepseek-giay-phep.md)).
