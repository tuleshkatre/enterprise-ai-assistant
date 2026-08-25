import pytest
from pydantic import ValidationError

from app.utils.pagination import PaginationParams, paginated_response


def test_pagination_requires_page_and_size_together():
    with pytest.raises(ValidationError):
        PaginationParams(page=1)


def test_paginated_response_contains_expected_metadata():
    response = paginated_response([{"id": 1}], total=11, page=2, size=10)
    assert response == {
        "items": [{"id": 1}],
        "page": 2,
        "size": 10,
        "total": 11,
        "total_pages": 2,
    }
