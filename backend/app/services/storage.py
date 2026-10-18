"""Lớp trừu tượng lưu file (ADR-0007): MinIO qua boto3, dùng chung cho API và worker."""

import logging
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Protocol

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

from app.core.config import settings

logger = logging.getLogger(__name__)


@dataclass
class StoredObject:
    body: Iterator[bytes]
    length: int
    total: int
    content_range: str | None = None
    headers: dict[str, str] = field(default_factory=dict)


class Storage(Protocol):
    def ensure_bucket(self) -> None: ...
    def put(self, key: str, data: bytes, content_type: str) -> None: ...
    def get_bytes(self, key: str) -> bytes: ...
    def open(self, key: str, byte_range: str | None = None) -> StoredObject: ...
    def delete_prefix(self, prefix: str) -> None: ...


class ObjectNotFound(Exception):
    pass


class InvalidRange(Exception):
    pass


class S3Storage:
    def __init__(self) -> None:
        self.bucket = settings.s3_bucket
        self.client = boto3.client(
            "s3",
            endpoint_url=settings.s3_endpoint,
            aws_access_key_id=settings.minio_root_user,
            aws_secret_access_key=settings.minio_root_password,
            region_name="us-east-1",
            config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
        )
        self._bucket_ready = False

    def ensure_bucket(self) -> None:
        if self._bucket_ready:
            return
        try:
            self.client.head_bucket(Bucket=self.bucket)
        except ClientError:
            self.client.create_bucket(Bucket=self.bucket)
            logger.info("Created bucket %s", self.bucket)
        self._bucket_ready = True

    def put(self, key: str, data: bytes, content_type: str) -> None:
        self.ensure_bucket()
        self.client.put_object(Bucket=self.bucket, Key=key, Body=data, ContentType=content_type)

    def get_bytes(self, key: str) -> bytes:
        try:
            obj = self.client.get_object(Bucket=self.bucket, Key=key)
        except ClientError as exc:
            raise ObjectNotFound(key) from exc
        return obj["Body"].read()

    def open(self, key: str, byte_range: str | None = None) -> StoredObject:
        kwargs = {"Bucket": self.bucket, "Key": key}
        if byte_range:
            kwargs["Range"] = byte_range
        try:
            obj = self.client.get_object(**kwargs)
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") == "InvalidRange":
                raise InvalidRange(byte_range) from exc
            raise ObjectNotFound(key) from exc
        content_range = obj.get("ContentRange")
        total = int(content_range.rsplit("/", 1)[1]) if content_range else obj["ContentLength"]
        return StoredObject(
            body=obj["Body"].iter_chunks(64 * 1024),
            length=obj["ContentLength"],
            total=total,
            content_range=content_range,
        )

    def delete_prefix(self, prefix: str) -> None:
        paginator = self.client.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=self.bucket, Prefix=prefix):
            keys = [{"Key": o["Key"]} for o in page.get("Contents", [])]
            if keys:
                self.client.delete_objects(Bucket=self.bucket, Delete={"Objects": keys})


_storage: Storage | None = None


def get_storage() -> Storage:
    global _storage
    if _storage is None:
        _storage = S3Storage()
    return _storage


def lecture_prefix(user_id: object, lecture_id: object) -> str:
    return f"users/{user_id}/lectures/{lecture_id}/"
