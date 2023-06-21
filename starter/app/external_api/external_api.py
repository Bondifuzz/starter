from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from aiohttp import ClientSession

from .interfaces.pool_manager import PoolManagerAPI

if TYPE_CHECKING:
    from starter.app.settings import AppSettings


class ExternalAPI:

    _logger: logging.Logger
    _pool_mgr: PoolManagerAPI
    _session: ClientSession
    _is_closed: bool

    @property
    def pool_mgr(self):
        return self._pool_mgr

    async def _init(self, settings: AppSettings):
        self._is_closed = True
        self._pool_mgr = PoolManagerAPI(settings)
        self._logger = logging.getLogger("api.external")
        self._is_closed = False

    @staticmethod
    async def create(settings):
        _self = ExternalAPI()
        await _self._init(settings)
        return _self

    async def close(self):

        assert not self._is_closed, "External API sessions have been already closed"

        sessions = [
            self._pool_mgr,
        ]

        for session in sessions:
            await session.close()

        self._is_closed = True

    def __del__(self):
        if not self._is_closed:
            self._logger.error("External API sessions have not been closed")
