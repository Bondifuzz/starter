from __future__ import annotations

from typing import TYPE_CHECKING

from mqtransport import MQApp, SQSApp

from .starter import (
    MC_ClusterScaled,
    MC_FuzzerPodFinished,
    MC_ResourcesSync,
    MP_ResourcesSync,
    MP_RunFuzzer,
)

if TYPE_CHECKING:
    from starter.app.settings import AppSettings


class Producers:
    sch_fuzzer_run: MP_RunFuzzer
    sch_resource_sync: MP_ResourcesSync


class Consumers:
    st_fuzzer_finished: MC_FuzzerPodFinished
    st_resource_sync: MC_ResourcesSync
    st_cluster_scaled: MC_ClusterScaled


class MQAppState:
    producers: Producers
    consumers: Consumers


class MQAppInitializer:

    """The opposite version of MQApp to test starter service"""

    _settings: AppSettings
    _app: MQApp

    @property
    def app(self):
        return self._app

    def __init__(self, settings: AppSettings):
        self._settings = settings
        self._app = None

    async def do_init(self):

        self._app = await self._create_mq_app()
        self._app.state = MQAppState()

        try:
            await self._app.ping()
            await self._configure_channels()

        except:
            await self._app.shutdown()
            raise

    async def _create_mq_app(self):

        mq_broker = self._settings.message_queue.broker.lower()
        mq_settings = self._settings.message_queue

        if mq_broker == "sqs":
            return await SQSApp.create(
                mq_settings.username,
                mq_settings.password,
                mq_settings.region,
                mq_settings.url,
            )

        raise ValueError(f"Unsupported message broker: {mq_broker}")

    async def _create_own_channel(self):
        queues = self._settings.message_queue.queues
        ich = await self._app.create_consuming_channel(queues.scheduler)
        dlq = await self._app.create_producing_channel(queues.dlq)
        ich.use_dead_letter_queue(dlq)
        self._ich_starter = ich

    async def _create_other_channels(self):
        queues = self._settings.message_queue.queues
        och1 = await self._app.create_producing_channel(queues.starter)
        self._och_scheduler = och1

    def _setup_starter_communication(self):

        state: MQAppState = self.app.state
        ich = self._ich_starter
        och = self._och_scheduler

        # Incoming messages
        consumers = Consumers()
        consumers.st_fuzzer_finished = MC_FuzzerPodFinished()
        consumers.st_cluster_scaled = MC_ClusterScaled()
        consumers.st_resource_sync = MC_ResourcesSync()

        ich.add_consumer(consumers.st_fuzzer_finished)
        ich.add_consumer(consumers.st_resource_sync)
        ich.add_consumer(consumers.st_cluster_scaled)

        # Outcoming messages
        producers = Producers()
        producers.sch_fuzzer_run = MP_RunFuzzer()
        producers.sch_resource_sync = MP_ResourcesSync()

        och.add_producer(producers.sch_fuzzer_run)
        och.add_producer(producers.sch_resource_sync)

        state.consumers = consumers
        state.producers = producers

    async def _configure_channels(self):
        await self._create_own_channel()
        await self._create_other_channels()
        self._setup_starter_communication()


async def mq_init(settings: AppSettings):
    initializer = MQAppInitializer(settings)
    await initializer.do_init()
    return initializer.app
