# Lệnh phát triển Stugen (ADR-0016). Backend test/lint chạy trong container `api`.
set windows-shell := ["powershell.exe", "-NoLogo", "-Command"]

default:
    @just --list

up:
    docker compose up -d --build

down:
    docker compose down

logs:
    docker compose logs -f api worker

migrate:
    docker compose exec api alembic upgrade head

revision message:
    docker compose exec api alembic revision --autogenerate -m "{{message}}"

test *args:
    docker compose exec api pytest {{args}}

lint:
    docker compose exec api ruff check .
    docker compose exec api ruff format --check .
    cd frontend; npm run lint
    cd frontend; npm run typecheck

fmt:
    docker compose exec api ruff check --fix .
    docker compose exec api ruff format .
    cd frontend; npx prettier --write src

gen-api:
    cd frontend; npm run gen:api

# CHỈ DÙNG LOCAL: tạo phiên đăng nhập dev, in token cho cookie sid
session email="dev@example.com":
    docker compose exec api python -m scripts.dev_session {{email}}
