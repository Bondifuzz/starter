"""
## Kubernetes API module
"""

from __future__ import annotations

from logging import getLogger
from typing import TYPE_CHECKING, Dict, List

from starter.app.kubernetes.client import KubernetesClient
from starter.app.util.labels import parse_bondifuzz_labels
from starter.app.util.resources import CpuResources, RamResources

from .pod_registry import FuzzerPod, FuzzerPodRegistry

if TYPE_CHECKING:

    # fmt: off
    # isort: off
    from kubernetes_asyncio.client import V1Pod
    from kubernetes_asyncio.client.models.v1_pod_spec import V1PodSpec
    from kubernetes_asyncio.client.models.v1_pod_status import V1PodStatus
    from kubernetes_asyncio.client.models.v1_object_meta import V1ObjectMeta
    from kubernetes_asyncio.client.models.v1_resource_requirements import V1ResourceRequirements
    from kubernetes_asyncio.client.models.v1_container import V1Container
    # isort: on
    # fmt: on


def get_pod_resources(pod: V1Pod):

    spec: V1PodSpec = pod.spec
    containers: List[V1Container] = spec.containers
    meta: V1ObjectMeta = pod.metadata
    pod_name = meta.name

    cpu_total = 0
    ram_total = 0

    for container in containers:

        resources: V1ResourceRequirements = container.resources
        requests: Dict[str, str] = resources.requests

        try:
            cpu_total += CpuResources.from_string(requests["cpu"])
            ram_total += RamResources.from_string(requests["memory"])

        except (KeyError, ValueError) as e:
            msg = "Failed to parse 'requests' block of container '%s.%s'"
            raise RuntimeError(msg % (pod_name, container.name)) from e

    return cpu_total, ram_total


def parse_k8s_pod(pod: V1Pod):

    status: V1PodStatus = pod.status
    meta: V1ObjectMeta = pod.metadata
    pod_name: str = meta.name

    labels = parse_bondifuzz_labels(meta.labels)
    cpu_usage, ram_usage = get_pod_resources(pod)

    try:
        pod = FuzzerPod(
            # V1Pod
            name=pod_name,
            phase=status.phase,
            start_time=status.start_time,
            displaced="displaced_at" in labels,
            deleting=False,
            cpu=cpu_usage,
            ram=ram_usage,
            # Suitcase
            user_id=labels["user_id"],
            project_id=labels["project_id"],
            pool_id=labels["pool_id"],
            fuzzer_id=labels["fuzzer_id"],
            fuzzer_rev=labels["fuzzer_rev"],
            agent_mode=labels["agent_mode"],
            fuzzer_lang=labels["fuzzer_lang"],
            fuzzer_engine=labels["fuzzer_engine"],
            session_id=labels["session_id"],
            # Pre-saved logs
            agent_logs=None,
            sandbox_logs=None,
            logs_saved=False,
        )

    except KeyError as e:
        msg = "Failed to parse fuzzer pod '%s'. No label '%s'"
        raise RuntimeError(msg % (pod_name, str(e))) from e

    return pod


async def pod_registry_init(k8s_client: KubernetesClient):

    registry = FuzzerPodRegistry()
    async for pod in k8s_client.list_fuzzer_pods():
        registry.add_pod(parse_k8s_pod(pod))

    getLogger("registry.pods").info(
        "Loaded %d pods to registry",
        len(registry.list_pods()),
    )

    return registry
