from typing import Literal

from pydantic import BaseModel


class HealthOut(BaseModel):
    status: Literal["ok", "error"]
    db: Literal["ok", "error"]
    redis: Literal["ok", "error"]


class ErrorOut(BaseModel):
    code: str
    detail: str


class Page[T](BaseModel):
    items: list[T]
    page: int
    page_size: int
    total: int
