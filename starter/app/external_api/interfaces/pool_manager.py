from typing import AsyncIterator, Tuple

from aiohttp_sse_client import client as sse_client

from starter.app.external_api.models import PMGRPool
from starter.app.settings import AppSettings
from starter.app.util.logging import PrefixedLogger

from .base import ExternalAPIBase


class PoolManagerAPI(ExternalAPIBase):

    """Communication with Pool manager"""

    def __init__(self, settings: AppSettings):
        super().__init__(settings.api_endpoints.pool_manager)
        self._base_path = "/api/v1/pools"
        self._setup_logging()

    def _setup_logging(self):
        extra = {"prefix": f"[{self.__class__.__name__}]:"}
        self._logger = PrefixedLogger(self._logger, extra)

    async def list_pools(self) -> AsyncIterator[PMGRPool]:

        url = self._base_path
        async for pool in self.paginate(url, PMGRPool):
            yield pool

    def _pool_event_source(self):
        return sse_client.EventSource(
            f"{self._base_path}/event-stream",
            session=self._session,
        )

    async def pool_event_stream(self) -> AsyncIterator[Tuple[str, str]]:
        async with self._pool_event_source() as event_source:
            async for event in event_source:
                yield event.type, event.data
