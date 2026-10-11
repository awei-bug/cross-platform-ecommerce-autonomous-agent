from datetime import datetime
from typing import Protocol

from app.schemas.products import ProductListItem


class ReadOnlyCommerceConnector(Protocol):
    """Boundary implemented by each official platform Open API adapter."""

    async def fetch_products(
        self, updated_after: datetime | None = None
    ) -> list[ProductListItem]: ...

    async def healthcheck(self) -> bool: ...
