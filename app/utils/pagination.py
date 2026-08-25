"""Optional pagination helpers that preserve legacy list responses."""

import math

from pydantic import BaseModel, Field, model_validator


class PaginationParams(BaseModel):
    page: int | None = Field(default=None, ge=1)
    size: int | None = Field(default=None, ge=1, le=100)

    @model_validator(mode="after")
    def require_page_and_size_together(self) -> "PaginationParams":
        if (self.page is None) != (self.size is None):
            raise ValueError("page and size must be provided together")
        return self

    @property
    def enabled(self) -> bool:
        return self.page is not None


def paginated_response(items: list[dict], total: int, page: int, size: int) -> dict:
    return {
        "items": items,
        "page": page,
        "size": size,
        "total": total,
        "total_pages": math.ceil(total / size) if total else 0,
    }
