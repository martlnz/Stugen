import hashlib
import secrets


def new_session_token() -> str:
    """Token ngẫu nhiên 32 byte đặt trong cookie `sid` (ADR-0005)."""
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    """DB chỉ lưu SHA-256 (hex) của token."""
    return hashlib.sha256(token.encode()).hexdigest()


def safe_next_path(value: str | None, default: str = "/library") -> str:
    """Chỉ nhận đường dẫn nội bộ bắt đầu bằng `/` (chống open redirect)."""
    if not value or not value.startswith("/") or value.startswith("//") or "\\" in value:
        return default
    return value
