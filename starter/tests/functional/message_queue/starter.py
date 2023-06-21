from __future__ import annotations

import asyncio

from mqtransport.participants import Consumer, Producer

from starter.app.message_queue.scheduler import MC_ResourcesSync as _MC_ResourcesSync
from starter.app.message_queue.scheduler import MC_RunFuzzer as _MC_RunFuzzer
from starter.app.message_queue.scheduler import MP_ClusterScaled as _MP_ClusterScaled
from starter.app.message_queue.scheduler import (
    MP_FuzzerPodFinished as _MP_FuzzerPodFinished,
)
from starter.app.message_queue.scheduler import MP_ResourcesSync as _MP_ResourcesSync


class MP_RunFuzzer(Producer):

    """Producer for MC_RunFuzzer"""

    name = _MC_RunFuzzer.name

    class Model(_MC_RunFuzzer.Model):
        pass


class MP_ResourcesSync(Producer):

    """Producer for MC_ResourcesSync"""

    name = _MC_ResourcesSync.name

    class Model(_MC_ResourcesSync.Model):
        pass


class MC_Test(Consumer):

    """Saves incoming messages to queue for further processing"""

    _event_queue: asyncio.Queue

    def __init__(self):
        super().__init__()
        self._event_queue = asyncio.Queue()

    async def consume(self, msg, app):
        await self._event_queue.put(msg)

    async def get_next_event(self, timeout=10):
        return await asyncio.wait_for(self._event_queue.get(), timeout)


class MC_FuzzerPodFinished(MC_Test):

    """Consumer for MP_FuzzerPorFinished"""

    name = _MP_FuzzerPodFinished.name

    class Model(_MP_FuzzerPodFinished.Model):
        pass

    async def get_next_event(self, timeout=10) -> Model:
        return await super().get_next_event(timeout)


class MC_ClusterScaled(MC_Test):

    """Consumer for MP_ClusterScaled"""

    name = _MP_ClusterScaled.name

    class Model(_MP_ClusterScaled.Model):
        pass

    async def get_next_event(self, timeout=10) -> Model:
        return await super().get_next_event(timeout)


class MC_ResourcesSync(MC_Test):

    """Consumer for MP_ResourcesSync"""

    name = _MP_ResourcesSync.name

    class Model(_MP_ResourcesSync.Model):
        pass

    async def get_next_event(self, timeout=10) -> Model:
        return await super().get_next_event(timeout)
