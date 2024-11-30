from typing import Annotated

from fastapi import Query


# Pagination parameters
PageParam = Annotated[int, Query(ge=1, description="Page number")]
LimitParam = Annotated[int, Query(ge=1, le=100, description="Items per page")]
