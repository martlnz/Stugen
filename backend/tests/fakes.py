import re

from app.services.storage import InvalidRange, ObjectNotFound, StoredObject


class MemoryStorage:
    """Storage trong bộ nhớ cho test (cùng giao diện với S3Storage)."""

    def __init__(self) -> None:
        self.objects: dict[str, tuple[bytes, str]] = {}

    def ensure_bucket(self) -> None:
        pass

    def put(self, key: str, data: bytes, content_type: str) -> None:
        self.objects[key] = (data, content_type)

    def get_bytes(self, key: str) -> bytes:
        if key not in self.objects:
            raise ObjectNotFound(key)
        return self.objects[key][0]

    def open(self, key: str, byte_range: str | None = None) -> StoredObject:
        data = self.get_bytes(key)
        total = len(data)
        if not byte_range:
            return StoredObject(body=iter([data]), length=total, total=total)
        m = re.fullmatch(r"bytes=(\d*)-(\d*)", byte_range)
        if not m or int(m.group(1) or 0) >= total:
            raise InvalidRange(byte_range)
        start = int(m.group(1) or 0)
        end = min(int(m.group(2)) if m.group(2) else total - 1, total - 1)
        chunk = data[start : end + 1]
        return StoredObject(
            body=iter([chunk]),
            length=len(chunk),
            total=total,
            content_range=f"bytes {start}-{end}/{total}",
        )

    def delete_prefix(self, prefix: str) -> None:
        for key in [k for k in self.objects if k.startswith(prefix)]:
            del self.objects[key]
