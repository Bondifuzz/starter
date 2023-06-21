import asyncio
from collections import defaultdict
from typing import List

from starter.app.kubernetes.client import KubernetesClient
from starter.app.kubernetes.pods.registry import FuzzerPod
from starter.app.kubernetes.pods.registry.pod_registry import FuzzerPodRegistry


def _filter_suitable_pods(pods: List[FuzzerPod], pool_id: str):
    def filter_func(pod: FuzzerPod):
        return (
            pod.pool_id == pool_id
            and pod.agent_mode == "fuzzing"
            and pod.phase == "Running"
        )

    return list(filter(filter_func, pods))


def _select_suitable_pods_for_displacement(pods: List[FuzzerPod]):

    instances = defaultdict(int)
    for pod in pods:
        instances[(pod.fuzzer_id, pod.fuzzer_rev)] += 1

    def key(pod: FuzzerPod):
        return instances[(pod.fuzzer_id, pod.fuzzer_rev)], pod.start_time

    return sorted(pods, key=key)


def select_pods_for_displacement(pods: List[FuzzerPod], pool_id: str):

    """
    Select a pod for displacement:
        1. Filter pods which are
            - Are ready and running now
            - Running in pool with `pool_id`
            - Fuzzer mode is *fuzzing*
        2. Calculate pod count for each <`fuzzer_id`, `fuzzer_rev`> pair
        3. Sort filtered pods by:
            - Pod count
            - Pod start date
        4. Return first item of the sorted list
    """

    suitable_pods = _filter_suitable_pods(pods, pool_id)
    return _select_suitable_pods_for_displacement(suitable_pods)


async def _displace_pods(
    pods: List[str],
    pod_regitry: FuzzerPodRegistry,
    k8s_client: KubernetesClient,
):
    async def displace_pod(pod_name: str):
        pod_regitry.displace_pod(pod_name)
        await k8s_client.displace_fuzzer_pod(pod_name)

    tasks = []
    for pod in pods:
        tasks.append(displace_pod(pod))

    await asyncio.gather(*tasks)


async def try_displace_pods(
    pool_id: str,
    pod_regitry: FuzzerPodRegistry,
    k8s_client: KubernetesClient,
    cpu_required: int,
    ram_required: int,
):
    pods_to_displace = []
    pods = pod_regitry.list_pods()
    displacement_needed = False

    for pod in select_pods_for_displacement(pods, pool_id):
        pods_to_displace.append(pod.name)
        cpu_required -= pod.cpu
        ram_required -= pod.ram

        if cpu_required <= 0 and ram_required <= 0:
            displacement_needed = True
            break

    if displacement_needed:
        await _displace_pods(
            pods_to_displace,
            pod_regitry,
            k8s_client,
        )
