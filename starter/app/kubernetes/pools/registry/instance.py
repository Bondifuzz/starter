from starter.app.external_api.external_api import ExternalAPI
from starter.app.kubernetes.pods.registry import FuzzerPodRegistry

from .pool_registry import PoolRegistry


async def pool_registry_init(
    pod_registry: FuzzerPodRegistry,
    eapi: ExternalAPI,
):

    #
    # Call pool manager API to list pools
    #

    registry = PoolRegistry()
    async for pool in eapi.pool_mgr.list_pools():
        is_locked = pool.operation is not None
        rs_pool = registry.create_pool(pool.id, is_locked)
        for node in pool.rs_avail.nodes:
            rs_pool.add_node(
                node.name,
                node.cpu,
                node.ram,
            )

    #
    # Running pods consume resources
    # We must reflect this in pool registry
    #

    for pod in pod_registry.list_pods():
        registry.allocate_resources(
            pod.pool_id,
            pod.cpu,
            pod.ram,
        )

    return registry
