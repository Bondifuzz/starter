import asyncio
from logging import getLogger

from aiohttp import ClientPayloadError

from starter.app.external_api.external_api import ExternalAPI
from starter.app.kubernetes.pools.events.event_handler import PoolEventHandler
from starter.app.util.delay import delay


class PoolEventListener:

    _handler: PoolEventHandler
    _eapi: ExternalAPI

    def __init__(
        self,
        event_handler: PoolEventHandler,
        external_api: ExternalAPI,
    ):
        self._lock = asyncio.Lock()
        self._logger = getLogger("pool.events")
        self._handler = event_handler
        self._eapi = external_api
        self._is_closed = False
        self._task = None

    async def _event_watch(self):
        event_stream = self._eapi.pool_mgr.pool_event_stream()
        async for event_type, message in event_stream:
            await self._handler.handle(event_type, message)

    async def _event_loop(self):

        self._logger.info("Pool event listener is running")

        while True:
            try:
                await self._event_watch()
            except asyncio.CancelledError:
                break
            except asyncio.TimeoutError:
                continue  # reconnect on client timeout
            except ClientPayloadError:
                continue  # reconnect on failures
            except:
                msg = "Unhandled error in pool event listener"
                self._logger.exception(msg)
                await delay()

    async def start(self):

        assert self._task is None, "Already started"

        loop = asyncio.get_running_loop()
        self._task = loop.create_task(self._event_loop())

    async def stop(self):

        assert self._task is not None, "Not started yet"

        async with self._lock:
            self._task.cancel()
            self._task = None

    async def close(self):

        assert not self._is_closed, "Closed twice"

        if self._task:
            await self.stop()

        self._is_closed = True
