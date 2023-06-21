from __future__ import annotations

import logging
import os
from contextlib import AsyncExitStack
from random import randint
from typing import TYPE_CHECKING, Optional

from kubernetes_asyncio import config, watch
from kubernetes_asyncio.client import ApiClient
from kubernetes_asyncio.client.api.core_v1_api import CoreV1Api
from kubernetes_asyncio.config.config_exception import ConfigException

from starter.app.util.images import test_run_image_name

from ..settings import AppSettings
from .errors import KubernetesInitError, wrap_k8s_errors

if TYPE_CHECKING:
    from kubernetes_asyncio.client import V1Pod
    from kubernetes_asyncio.client.models.v1_object_meta import V1ObjectMeta
    from kubernetes_asyncio.client.models.v1_pod_status import V1PodStatus


class KubernetesInitializer:

    _v1: CoreV1Api
    _client: ApiClient
    _exit_stack: Optional[AsyncExitStack]
    _logger: logging.Logger
    _init_label: str
    _namespace: str
    _image: str

    @staticmethod
    async def _create_client():

        try:
            if "KUBERNETES_PORT" in os.environ:
                config.load_incluster_config()
            else:
                await config.load_kube_config()

        except ConfigException as e:
            raise KubernetesInitError("Failed to load kube config") from e

        exit_stack = AsyncExitStack()
        client = await exit_stack.enter_async_context(ApiClient())
        v1 = CoreV1Api(client)

        return exit_stack, client, v1

    async def _init(self, settings: AppSettings):

        self._init_label = "starter-init"
        self._logger = logging.getLogger("k8s.init")
        self._namespace = settings.fuzzer_pod.namespace
        self._image = test_run_image_name(settings)
        self._exit_stack = None
        self._is_closed = True

        exit_stack, client, v1 = await self._create_client()
        self._is_closed = False

        self._exit_stack = exit_stack
        self._client = client
        self._v1 = v1

    async def create(settings: AppSettings) -> KubernetesInitializer:
        _self = KubernetesInitializer()
        await _self._init(settings)
        return _self

    @wrap_k8s_errors
    async def _check_pod_create_permission(self, pod_name: str):

        pod_body = {
            "apiVersion": "v1",
            "kind": "Pod",
            "metadata": {
                "name": pod_name,
                "labels": {"app": self._init_label},
            },
            "spec": {
                "restartPolicy": "Never",
                "containers": [
                    {
                        "name": "sleep",
                        "image": self._image,
                        "command": ["echo", "lalala"],
                    }
                ],
                "imagePullSecrets": [
                    {"name": "regcred"},
                ],
            },
        }

        self._logger.info(f"Creating pod '{pod_name}'")
        await self._v1.create_namespaced_pod(self._namespace, body=pod_body)

    @wrap_k8s_errors
    async def _check_pod_read_permission(self, pod_name: str):
        await self._v1.read_namespaced_pod(pod_name, self._namespace)

    @wrap_k8s_errors
    async def _check_pod_watch_permission(self, pod_name: str):

        w = watch.Watch()
        result = False

        kw = {
            "namespace": self._namespace,
            "timeout_seconds": 60,
        }

        async with w.stream(self._v1.list_namespaced_pod, **kw) as stream:
            async for event in stream:
                obj: V1Pod = event["object"]
                status: V1PodStatus = obj.status
                metadata: V1ObjectMeta = obj.metadata
                if metadata.name == pod_name:
                    if status.phase == "Succeeded":
                        result = True
                        break

        if not result:
            raise KubernetesInitError("Pod completion event has not been catched")

    @wrap_k8s_errors
    async def _check_pod_patch_permission(self, pod_name: str):

        obj = {
            "metadata": {
                "labels": {
                    "patch-test": "passed",
                }
            }
        }

        await self._v1.patch_namespaced_pod(pod_name, self._namespace, obj)

    @wrap_k8s_errors
    async def _check_pod_read_log_permission(self, pod_name: str):
        await self._v1.read_namespaced_pod_log(pod_name, self._namespace)

    @wrap_k8s_errors
    async def _check_pod_delete_permission(self):
        kw = {"label_selector": f"app={self._init_label}"}
        await self._v1.delete_collection_namespaced_pod(self._namespace, **kw)

    def get_init_tasks(self):
        pod_name = "starter-test-" + str(randint(0, 100000000))
        yield "Pod create permission", self._check_pod_create_permission(pod_name)
        yield "Pod read permission", self._check_pod_read_permission(pod_name)
        yield "Pod watch permission", self._check_pod_watch_permission(pod_name)
        yield "Pod patch permission", self._check_pod_patch_permission(pod_name)
        yield "Pod read log permission", self._check_pod_read_log_permission(pod_name)
        yield "Pod delete permission", self._check_pod_delete_permission()

    async def do_init(self):

        try:
            self._logger.info("Initializing k8s...")
            for name, task in self.get_init_tasks():
                self._logger.info("Performing '%s'", name)
                await task

            self._logger.info("Initializing k8s... OK")

        finally:
            await self.close()

    async def close(self):

        assert not self._is_closed, "Closed twice"

        if self._exit_stack:
            await self._exit_stack.aclose()
            self._exit_stack = None

        self._is_closed = True

    def __del__(self):
        if not self._is_closed:
            self._logger.error("Kubernetes connection has not been closed")
