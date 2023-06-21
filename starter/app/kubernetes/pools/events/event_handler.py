from logging import getLogger

from charset_normalizer import logging

from starter.app.kubernetes.client import KubernetesClient
from starter.app.util.speedup import json

from ..registry import PoolRegistry
from .events import (
    PoolCreatedEvent,
    PoolCreatingEvent,
    PoolDeletedEvent,
    PoolDeletingEvent,
    PoolEventType,
    PoolNodeAddedEvent,
    PoolNodeRemovedEvent,
    PoolUpdatedEvent,
    PoolUpdatingEvent,
)


class PoolEventHandler:

    _registry: PoolRegistry
    _logger: logging.Logger
    _k8s_client: KubernetesClient

    def __init__(
        self,
        pool_registry: PoolRegistry,
        k8s_client: KubernetesClient,
    ):
        self._logger = getLogger("pool.events")
        self._registry = pool_registry
        self._k8s_client = k8s_client

    async def handle(self, event_type: str, raw_data: str):

        if event_type == "ping":
            return

        if event_type == PoolEventType.creating:

            pool_event = PoolCreatingEvent.parse_obj(
                json.loads(raw_data),
            )

            self._registry.create_pool(
                pool_event.pool_id,
                locked=True,
            )

            self._logger.debug(
                "Pool <id='%s'> creation started",
                pool_event.pool_id,
            )

        elif event_type == PoolEventType.created:

            pool_event = PoolCreatedEvent.parse_obj(
                json.loads(raw_data),
            )

            self._registry.unlock_pool(
                pool_event.pool_id,
            )

            self._logger.debug(
                "Pool <id='%s'> creation finished",
                pool_event.pool_id,
            )

        elif event_type == PoolEventType.updating:

            pool_event = PoolUpdatingEvent.parse_obj(
                json.loads(raw_data),
            )

            self._registry.lock_pool(
                pool_event.pool_id,
            )

            await self._k8s_client.delete_fuzzer_pods(
                pool_id=pool_event.pool_id,
            )

            self._logger.debug(
                "Pool <id='%s'> update started",
                pool_event.pool_id,
            )

        elif event_type == PoolEventType.updated:

            pool_event = PoolUpdatedEvent.parse_obj(
                json.loads(raw_data),
            )

            self._registry.unlock_pool(
                pool_event.pool_id,
            )

            await self._k8s_client.delete_fuzzer_pods(
                pool_id=pool_event.pool_id,
            )

            self._logger.debug(
                "Pool <id='%s'> update finished",
                pool_event.pool_id,
            )

        elif event_type == PoolEventType.deleting:

            pool_event = PoolDeletingEvent.parse_obj(
                json.loads(raw_data),
            )

            self._registry.lock_pool(
                pool_event.pool_id,
            )

            await self._k8s_client.delete_fuzzer_pods(
                pool_id=pool_event.pool_id,
            )

            self._logger.debug(
                "Pool <id='%s'> deletion started",
                pool_event.pool_id,
            )

        elif event_type == PoolEventType.deleted:

            pool_event = PoolDeletedEvent.parse_obj(
                json.loads(raw_data),
            )

            self._registry.remove_pool(
                pool_event.pool_id,
            )

            self._logger.debug(
                "Pool <id='%s'> deletion finished",
                pool_event.pool_id,
            )

        elif event_type == PoolEventType.node_added:

            pool_event = PoolNodeAddedEvent.parse_obj(
                json.loads(raw_data),
            )

            self._registry.add_pool_node(
                pool_event.pool_id,
                pool_event.node_name,
                pool_event.cpu,
                pool_event.ram,
            )

            self._logger.debug(
                "Pool node added: <pool_id='%s', node_name='%s'>",
                pool_event.pool_id, pool_event.node_name,  # fmt: skip
            )

        elif event_type == PoolEventType.node_removed:

            pool_event = PoolNodeRemovedEvent.parse_obj(
                json.loads(raw_data),
            )

            self._registry.remove_pool_node(
                pool_event.pool_id,
                pool_event.node_name,
            )

            self._logger.debug(
                "Pool node removed: <pool_id='%s', node_name='%s'>",
                pool_event.pool_id, pool_event.node_name,  # fmt: skip
            )

        else:
            msg = "Unknown event type: %s"
            self._logger.warning(msg, event_type)
