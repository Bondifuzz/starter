import logging
from dataclasses import dataclass
from typing import Dict

from starter.app.util.logging import PrefixedLogger

from .errors import (
    PoolCapacityExceededError,
    PoolLockedError,
    PoolNodeAlreadyExistsError,
    PoolNodeNotFoundError,
    PoolNoResourcesLeftError,
    PoolOverflowError,
    PoolUnderflowError,
)


@dataclass
class PoolNode:
    name: str
    cpu: int
    ram: int

    def dict(self):
        return self.__dict__


class ResourcePool:

    _id: str
    _logger: logging.Logger

    _nodes: Dict[str, PoolNode]
    _cpu_used: int
    _ram_used: int
    _cpu_limit: int
    _ram_limit: int
    _locked: bool

    def __init__(self, pool_id: str, locked: bool):
        self._id = pool_id
        self._cpu_used = 0
        self._ram_used = 0
        self._cpu_limit = 0
        self._ram_limit = 0
        self._locked = locked
        self._nodes = {}
        self._setup_logging()

    def _setup_logging(self):
        logger = logging.getLogger("pool")
        extra = {"prefix": f"[Pool <id='{self._id}'>]"}
        self._logger = PrefixedLogger(logger, extra)

    def resources_left(self):
        return (
            self._cpu_limit - self._cpu_used,
            self._ram_limit - self._ram_used,
        )

    def add_node(self, node_name: str, cpu: int, ram: int):

        assert cpu > 0, "cpu must be greater than zero"
        assert ram > 0, "ram must be greater than zero"

        if node_name in self._nodes:
            msg = f"Node '{node_name}' already exists in pool '{self._id}'"
            raise PoolNodeAlreadyExistsError(msg)

        self._cpu_limit += cpu
        self._ram_limit += ram
        self._nodes[node_name] = PoolNode(node_name, cpu, ram)

        msg = "Node added: <name='%s', cpu=%dm, ram=%dMi>"
        self._logger.debug(msg, node_name, cpu, ram)

        msg = "Summary: <cpu_total=%dm, ram_total=%dMi, node_count=%d>"
        args = self._cpu_limit, self._ram_limit, self.node_count
        self._logger.debug(msg, *args)

    def remove_node(self, node_name: str):

        try:
            node = self._nodes.pop(node_name)
        except KeyError as e:
            msg = f"Node '{node_name}' not found in pool '{self._id}'"
            raise PoolNodeNotFoundError(msg) from e

        self._cpu_limit -= node.cpu
        self._ram_limit -= node.ram
        assert self._cpu_limit >= 0
        assert self._ram_limit >= 0

        msg = "Node removed: <name='%s', cpu=%dm, ram=%dMi>"
        self._logger.debug(msg, node.name, node.cpu, node.ram)

        msg = "Summary: <cpu_total=%dm, ram_total=%dMi, node_count=%d>"
        args = self._cpu_limit, self._ram_limit, self.node_count
        self._logger.debug(msg, *args)

    def allocate(self, cpu: int, ram: int):

        if self._locked:
            raise PoolLockedError("Pool locked")

        if cpu > self._cpu_limit or ram > self._ram_limit:
            msg = "Requested resources exceed pool capacity: req/max <cpu=%s, ram=%s>"
            rs_cpu = f"[{cpu}m/{self._cpu_limit}m]"
            rs_ram = f"[{ram}Mi/{self._ram_limit}Mi]"
            self._logger.warning(msg, rs_cpu, rs_ram)
            raise PoolCapacityExceededError(msg % (rs_cpu, rs_ram))

        if (
            self._cpu_used > self._cpu_limit  # fmt: skip
            or self._ram_used > self._ram_limit
        ):
            msg = "Pool overflowed: cur/max <cpu=%s, ram=%s>"
            rs_cpu = f"[{self._cpu_used}m/{self._cpu_limit}m]"
            rs_ram = f"[{self._ram_used}Mi/{self._ram_limit}Mi]"
            self._logger.warning(msg, rs_cpu, rs_ram)
            raise PoolOverflowError(msg % (rs_cpu, rs_ram))

        if (
            self._cpu_used + cpu > self._cpu_limit  # fmt: skip
            or self._ram_used + ram > self._ram_limit
        ):
            msg = "No resources left: req/left <cpu=%s, ram=%s>"
            rs_cpu = f"[{cpu}m/{self._cpu_limit - self._cpu_used}m]"
            rs_ram = f"[{ram}Mi/{self._ram_limit - self._ram_used}Mi]"
            self._logger.debug(msg, rs_cpu, rs_ram)
            raise PoolNoResourcesLeftError(msg % (rs_cpu, rs_ram))

        self._cpu_used += cpu
        self._ram_used += ram

        msg = "Resources allocated: cur/max <cpu=%s, ram=%s>"
        rs_cpu = f"[{self._cpu_used}m/{self._cpu_limit}m]"
        rs_ram = f"[{self._ram_used}Mi/{self._ram_limit}Mi]"
        self._logger.debug(msg, rs_cpu, rs_ram)

    def free(self, cpu: int, ram: int):

        if self._cpu_used - cpu < 0 or self._ram_used - ram < 0:
            msg = "Pool underflow: <cpu=%s, ram=%s>"
            rs_cpu = f"[{self._cpu_used}m->{self._cpu_used - cpu}m]"
            rs_ram = f"[{self._ram_used}Mi->{self._ram_used - ram}Mi]"
            self._logger.error(msg, rs_cpu, rs_ram)
            raise PoolUnderflowError(msg % (rs_cpu, rs_ram))

        self._cpu_used -= cpu
        self._ram_used -= ram

        msg = "Resources freed: cur/max <cpu=%s, ram=%s>"
        rs_cpu = f"[{self._cpu_used}m/{self._cpu_limit}m]"
        rs_ram = f"[{self._ram_used}Mi/{self._ram_limit}Mi]"
        self._logger.debug(msg, rs_cpu, rs_ram)

    def lock(self):
        self._locked = True

    def unlock(self):
        self._locked = False

    @property
    def cpu_used(self):
        return self._cpu_used

    @property
    def ram_used(self):
        return self._ram_used

    @property
    def cpu_limit(self):
        return self._cpu_limit

    @property
    def ram_limit(self):
        return self._ram_limit

    @property
    def locked(self):
        return self._locked

    @property
    def id(self):
        return self._id

    @property
    def node_count(self):
        return len(self._nodes)

    @property
    def nodes(self):
        return list(self._nodes.values())
