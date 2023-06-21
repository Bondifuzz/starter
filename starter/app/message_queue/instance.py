from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import FastAPI
from mqtransport import MQApp, SQSApp

from .scheduler import MP_PodFinished

if TYPE_CHECKING:
    from ..database.abstract import IDatabase
    from ..kubernetes.client import KubernetesClient
    from ..settings import AppSettings


class Producers:
    sch_pod_finished: MP_PodFinished


class MQAppState:
    k8s_client: KubernetesClient
    producers: Producers
    settings: AppSettings
    fastapi: FastAPI
    db: IDatabase


class MQAppInitializer:

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

    async def _create_other_channels(self):
        queues = self._settings.message_queue.queues
        och1 = await self._app.create_producing_channel(queues.scheduler)
        self._och_scheduler = och1

    def _setup_scheduler_communication(self):

        state: MQAppState = self.app.state
        och = self._och_scheduler

        # Outcoming messages
        producers = Producers()
        producers.sch_pod_finished = MP_PodFinished()
        och.add_producer(producers.sch_pod_finished)

        state.producers = producers

    async def _configure_channels(self):
        await self._create_other_channels()
        self._setup_scheduler_communication()


async def mq_init(settings: AppSettings):
    initializer = MQAppInitializer(settings)
    await initializer.do_init()
    return initializer.app
