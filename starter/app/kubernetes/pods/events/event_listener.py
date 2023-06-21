from __future__ import annotations

import asyncio
import logging
from contextlib import AsyncExitStack, asynccontextmanager
from typing import Optional

from kubernetes_asyncio import watch
from kubernetes_asyncio.client import ApiClient
from kubernetes_asyncio.client.api.core_v1_api import CoreV1Api

from starter.app.settings import AppSettings
from starter.app.util.delay import delay

from .event_handler import PodEventHandler


class PodEventListener:

    _v1: CoreV1Api
    _client: ApiClient
    _handler: PodEventHandler
    _exit_stack: Optional[AsyncExitStack]
    _lock: asyncio.Lock
    _task: asyncio.Task
    _namespace: str

    @staticmethod
    async def _create_client():

        exit_stack = AsyncExitStack()
        client = await exit_stack.enter_async_context(ApiClient())
        v1 = CoreV1Api(client)

        return exit_stack, client, v1

    async def _init(self, handler: PodEventHandler, settings: AppSettings):

        self._task = None
        self._is_closed = True
        self._exit_stack = None
        self._lock = asyncio.Lock()
        self._logger = logging.getLogger("k8s.listener")
        self._namespace = settings.fuzzer_pod.namespace
        self._handler = handler

        exit_stack, client, v1 = await self._create_client()
        self._is_closed = False

        self._exit_stack = exit_stack
        self._client = client
        self._v1 = v1

    @staticmethod
    async def create(
        handler: PodEventHandler,
        settings: AppSettings,
    ):
        _self = PodEventListener()
        await _self._init(handler, settings)
        return _self

    async def _event_handler(self, event: dict):
        try:
            await self._handler.handle(event["type"], event["object"])
        except Exception:
            msg = "Unhandled error in k8s event handler"
            self._logger.exception(msg)
            await delay()

    async def _event_watch(self):

        kwargs = {
            "namespace": self._namespace,
            "timeout_seconds": 300,
        }

        w = watch.Watch()
        async with w.stream(self._v1.list_namespaced_pod, **kwargs) as stream:
            async for event in stream:
                async with self._lock:
                    await self._event_handler(event)

    async def _event_loop(self):

        self._logger.info("Kubernetes listener is running")

        while True:
            try:
                await self._event_watch()
            except asyncio.CancelledError:
                break
            except asyncio.TimeoutError:
                continue
            except Exception:
                self._logger.exception("Unhandled error in k8s event listener")
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

    @asynccontextmanager
    async def pause(self):
        try:
            await self._lock.acquire()
            yield
        finally:
            self._lock.release()

    async def close(self):

        assert not self._is_closed, "Closed twice"

        if self._task:
            await self.stop()

        if self._exit_stack:
            await self._exit_stack.aclose()
            self._exit_stack = None

        self._is_closed = True

    def __del__(self):
        if not self._is_closed:
            self._logger.error("Kubernetes connection has not been closed")
