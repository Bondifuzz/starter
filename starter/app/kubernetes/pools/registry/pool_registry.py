from logging import getLogger
from typing import Dict

from .errors import PoolAlreadyExistsError, PoolNotFoundError
from .resource_pool import ResourcePool


class PoolRegistry:

    _pools: Dict[str, ResourcePool]

    def __init__(self):
        self._pools = {}
        self._logger = getLogger("pool.registry")

    def lock_pool(self, pool_id: str):
        self.find_pool(pool_id).lock()

    def unlock_pool(self, pool_id: str):
        self.find_pool(pool_id).unlock()

    def create_pool(self, pool_id: str, locked: bool):

        if pool_id in self._pools:
            raise PoolAlreadyExistsError(pool_id)

        msg = "Created new pool <id='%s', locked=%s>"
        self._logger.debug(msg, pool_id, locked)

        pool = ResourcePool(pool_id, locked)
        self._pools[pool_id] = pool
        return pool

    def remove_pool(self, pool_id: str):
        try:
            pool = self._pools.pop(pool_id)
        except KeyError as e:
            msg = f"Pool '{pool_id}' not found"
            raise PoolNotFoundError(msg) from e

        self._logger.debug("Removed pool <id='%s'>", pool.id)

    def find_pool(self, pool_id: str):

        try:
            res = self._pools[pool_id]
        except KeyError as e:
            msg = f"Pool '{pool_id}' not found"
            raise PoolNotFoundError(msg) from e

        return res

    def list_pools(self):
        return list(self._pools.values())

    def add_pool_node(self, pool_id: str, node_name: str, cpu: int, ram: int):
        self.find_pool(pool_id).add_node(node_name, cpu, ram)

    def remove_pool_node(self, pool_id: str, node_name: str):
        self.find_pool(pool_id).remove_node(node_name)

    def allocate_resources(self, pool_id: str, cpu: int, ram: int):
        self.find_pool(pool_id).allocate(cpu, ram)

    def resources_left(self, pool_id: str):
        return self.find_pool(pool_id).resources_left()

    def free_resources(self, pool_id: str, cpu: int, ram: int):
        self.find_pool(pool_id).free(cpu, ram)

    def has_pool(self, pool_id: str):
        return self._pools.get(pool_id) is not None
