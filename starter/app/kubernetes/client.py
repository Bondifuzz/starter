"""
## Kubernetes API module
"""

from __future__ import annotations

import logging
from contextlib import AsyncExitStack
from typing import TYPE_CHECKING, AsyncIterator, Optional

from kubernetes_asyncio.client import ApiClient
from kubernetes_asyncio.client.api.core_v1_api import CoreV1Api as BaseCoreV1Api

from starter.app.spec.agent.template import AgentSpecTemplate
from starter.app.util.labels import bondifuzz_key
from starter.app.util.resources import CpuResources, RamResources

from ..settings import AppSettings
from ..util.developer import testing_only

if TYPE_CHECKING:

    # fmt: off
    # isort: off
    from kubernetes_asyncio.client import V1Pod
    from kubernetes_asyncio.client.models.v1_list_meta import V1ListMeta
    from kubernetes_asyncio.client.models.v1_pod_list import V1PodList
    # isort: on
    # fmt: on

    V1PodIterator = AsyncIterator[V1Pod]


########################################
# Kubernetes API wrapper
########################################


class CoreV1Api(BaseCoreV1Api):
    async def list_namespaced_pod_iter(self, namespace, **kwargs) -> V1PodIterator:

        kwargs["limit"] = 100
        continuation_token = None

        while True:

            kwargs["_continue"] = continuation_token
            response: V1PodList = await self.list_namespaced_pod(
                namespace,
                **kwargs,
            )

            for item in response.items:
                yield item

            meta: V1ListMeta = response.metadata
            continuation_token = meta._continue

            if not continuation_token:
                break


class KubernetesClient:

    """
    Kubernetes API wrapper, implementing
    pod creation and deletion, querying
    node metrics and pod event monitoring
    """

    _v1: CoreV1Api
    _client: ApiClient
    _exit_stack: Optional[AsyncExitStack]
    _logger: logging.Logger
    _namespace: str
    _is_closed: bool
    _agent_template: AgentSpecTemplate

    @staticmethod
    async def _create_client():

        exit_stack = AsyncExitStack()
        client = await exit_stack.enter_async_context(ApiClient())
        v1 = CoreV1Api(client)

        return exit_stack, client, v1

    async def _init(self, settings: AppSettings):

        self._logger = logging.getLogger("k8s.client")
        self._namespace = settings.fuzzer_pod.namespace
        self._agent_template = AgentSpecTemplate("agent.yaml")
        self._exit_stack = None
        self._is_closed = True

        exit_stack, client, v1 = await self._create_client()
        self._is_closed = False

        self._exit_stack = exit_stack
        self._client = client
        self._v1 = v1

    async def create(settings: AppSettings) -> KubernetesClient:
        _self = KubernetesClient()
        await _self._init(settings)
        return _self

    async def create_fuzzer_pod(
        self,
        user_id: str,
        project_id: str,
        pool_id: str,
        fuzzer_id: str,
        fuzzer_rev: str,
        agent_mode: str,
        fuzzer_lang: str,
        fuzzer_engine: str,
        session_id: str,
        agent_image: str,
        sandbox_image: str,
        agent_cpu_usage: int,
        agent_ram_usage: int,
        sandbox_cpu_usage: int,
        sandbox_ram_usage: int,
        tmpfs_size: int,
    ) -> V1Pod:

        #
        # Set pod values
        #

        spec = self._agent_template.copy()
        spec.set_label(bondifuzz_key("agent_mode"), agent_mode)
        spec.set_label(bondifuzz_key("session_id"), session_id)
        spec.set_label(bondifuzz_key("user_id"), user_id)
        spec.set_label(bondifuzz_key("project_id"), project_id)
        spec.set_label(bondifuzz_key("pool_id"), pool_id)
        spec.set_label(bondifuzz_key("fuzzer_id"), fuzzer_id)
        spec.set_label(bondifuzz_key("fuzzer_rev"), fuzzer_rev)
        spec.set_label(bondifuzz_key("fuzzer_lang"), fuzzer_lang)
        spec.set_label(bondifuzz_key("fuzzer_engine"), fuzzer_engine)
        spec.set_tmpfs_size(RamResources.to_string(tmpfs_size))

        spec.set_node_selector(
            bondifuzz_key("pool_id"),
            pool_id,
        )

        spec.set_toleration(
            key=bondifuzz_key("pool_id"),
            value=pool_id,
            operator="Equal",
            effect="NoSchedule",
        )

        #
        # Set agent container values
        #

        agent_cpu = CpuResources.to_string(agent_cpu_usage)
        agent_ram = RamResources.to_string(agent_ram_usage)

        spec.set_agent_image_name(agent_image)
        spec.set_agent_rs_requests(agent_cpu, agent_ram)
        spec.set_agent_rs_limits(agent_cpu, agent_ram)

        spec.set_agent_env("AGENT_MODE", agent_mode)
        spec.set_agent_env("FUZZER_SESSION_ID", session_id)
        spec.set_agent_env("FUZZER_USER_ID", user_id)
        spec.set_agent_env("FUZZER_PROJECT_ID", project_id)
        spec.set_agent_env("FUZZER_POOL_ID", pool_id)
        spec.set_agent_env("FUZZER_ID", fuzzer_id)
        spec.set_agent_env("FUZZER_REV", fuzzer_rev)
        spec.set_agent_env("FUZZER_LANG", fuzzer_lang)
        spec.set_agent_env("FUZZER_ENGINE", fuzzer_engine)
        spec.set_agent_env("FUZZER_RAM_LIMIT", str(sandbox_ram_usage))

        #
        # Set sandbox container values
        #

        sandbox_cpu = CpuResources.to_string(sandbox_cpu_usage)
        sandbox_ram = RamResources.to_string(sandbox_ram_usage)

        spec.set_sandbox_image_name(sandbox_image)
        spec.set_sandbox_rs_requests(sandbox_cpu, sandbox_ram)
        spec.set_sandbox_rs_limits(sandbox_cpu, sandbox_ram)
        # spec._set_sandbox_env() # Must not set env in sandbox

        #
        # Create pod from generated spec
        #

        return await self._v1.create_namespaced_pod(
            self._namespace, spec.as_dict()  # fmt: skip
        )

    async def read_pod_log(self, pod_name: str, container_name: str):

        """
        Description:
            Reads pod's log.

        Args:
            name (str): name of the pod

        Returns:
            bytes: Logs of pod
        """

        return await self._v1.read_namespaced_pod_log(
            pod_name, self._namespace, container=container_name
        )

    async def delete_fuzzer_pod(self, name: str) -> bool:

        """
        Description:
            Stops and deletes pod

        Args:
            name (str): name of the pod

        Returns:
            None
        """

        await self._v1.delete_namespaced_pod(name, self._namespace)

    async def displace_fuzzer_pod(self, name: str) -> bool:

        """
        Description:
            Add label to pod which indicates that pod was displaced

        Args:
            name (str): name of the pod

        Returns:
            None
        """

        obj = {
            "metadata": {
                "labels": {
                    bondifuzz_key("displaced_at"): "",
                }
            }
        }

        await self._v1.patch_namespaced_pod(name, self._namespace, obj)

    @testing_only
    async def delete_all_fuzzer_pods(self):

        """
        Description:
            Destroys all pods in the namespace

        Returns:
            None
        """

        await self._v1.delete_collection_namespaced_pod(self._namespace)

    async def delete_fuzzer_pods(
        self,
        fuzzer_id: Optional[str] = None,
        pool_id: Optional[str] = None,
    ):
        assert fuzzer_id is not None or pool_id is not None

        # helper func, creates k8s selector
        def make_selector(key: str, val: str):
            return f"{bondifuzz_key(key)}={val}"

        label_selectors = []
        if pool_id is not None:
            label_selectors.append(make_selector("pool_id", pool_id))
        if fuzzer_id is not None:
            label_selectors.append(make_selector("fuzzer_id", fuzzer_id))

        kw = {"label_selector": ",".join(label_selectors)}
        await self._v1.delete_collection_namespaced_pod(self._namespace, **kw)

    def list_fuzzer_pods(self):
        kw = {"label_selector": bondifuzz_key("pool_id")}
        return self._v1.list_namespaced_pod_iter(self._namespace, **kw)

    async def close(self):

        assert not self._is_closed, "Closed twice"

        if self._exit_stack:
            await self._exit_stack.aclose()
            self._exit_stack = None

        self._is_closed = True

    def __del__(self):
        if not self._is_closed:
            self._logger.error("Kubernetes connection has not been closed")
