from copy import deepcopy
from typing import Any, Optional

from ..base.errors import SpecLoadError, SpecParseError
from ..base.spec import spec_get_item, spec_load, spec_set_item
from .errors import AgentSpecLoadError, AgentSpecParseError
from .spec import AgentSpec


class AgentSpecTemplate:

    _root: dict
    _agent_container: dict
    _sandbox_container: dict

    def _spec_get(self, key: str, root: Optional[dict] = None) -> Any:
        return spec_get_item(root or self._root, key)

    def _spec_set(self, key: str, value: Any, root: Optional[dict] = None) -> Any:
        return spec_set_item(root or self._root, key, value)

    def _spec_init_containers(self):

        key = ".spec.containers"
        containers = self._spec_get(key)

        if not isinstance(containers, list):
            msg = "Item 'containers' must be list"
            raise SpecParseError(key, msg)

        containers_kv = {c["name"]: c for c in containers}
        agent_container = containers_kv["agent"]
        sandbox_container = containers_kv["sandbox"]

        if not isinstance(agent_container, dict):
            msg = "Item 'containers[name=agent]' must be dict"
            raise SpecParseError(key, msg)

        if not isinstance(sandbox_container, dict):
            msg = "Item 'containers[name=sandbox]' must be dict"
            raise SpecParseError(key, msg)

        self._agent_container = agent_container
        self._sandbox_container = sandbox_container

    def _spec_init_labels(self):

        key = ".metadata.labels"
        labels = self._spec_get(key)

        if labels is not None:
            if not isinstance(labels, dict):
                msg = "Item 'labels' must be dict"
                raise SpecParseError(key, msg)
        else:
            self._spec_set(key, dict())

    def _spec_init_env(self, container: str):

        key = "env"
        env_list = self._spec_get(key, container)

        if env_list is not None:
            if not isinstance(env_list, list):
                msg = f"Item 'env' must be list (in '{container}')"
                raise SpecParseError(key, msg)
        else:
            self._spec_set(key, list(), container)

    def _spec_init_rs_requests(self, container):

        key = ".resources.requests"
        rs_requests = self._spec_get(key, container)

        if rs_requests is not None:
            if not isinstance(rs_requests, dict):
                msg = f"Item 'requests' must be dict (in '{container}')"
                raise SpecParseError(key, msg)
        else:
            self._spec_set(key, dict(), container)

    def _spec_init_rs_limits(self, container: str):

        key = ".resources.limits"
        rs_limits = self._spec_get(key, container)

        if rs_limits is not None:
            if not isinstance(rs_limits, dict):
                msg = f"Item 'limits' must be dict (in '{container}')"
                raise SpecParseError(key, msg)
        else:
            self._spec_set(key, dict(), container)

    def _spec_init_node_selector(self):

        key = ".spec.nodeSelector"
        node_selector = self._spec_get(key)

        if node_selector is not None:
            if not isinstance(node_selector, dict):
                msg = "Item 'limits' must be dict"
                raise SpecParseError(key, msg)
        else:
            self._spec_set(key, dict())

    def _spec_init_tolerations(self):

        key = ".spec.tolerations"
        tolerations = self._spec_get(key)

        if tolerations is not None:
            if not isinstance(tolerations, list):
                msg = "Item 'tolerations' must be list"
                raise SpecParseError(key, msg)
        else:
            self._spec_set(key, list())

    def _spec_init_tmpfs_volume(self):

        key = ".spec.volumes"
        volumes = self._spec_get(key)

        if not isinstance(volumes, list):
            msg = "Item 'volumes' must be list"
            raise SpecParseError(key, msg)

        try:
            tmpfs_vol = next(filter(lambda v: v["name"] == "tmpfs", volumes))
        except StopIteration:
            raise SpecParseError(key, "Couldn't find tmpfs volume")

        # Just ensure key present
        self._spec_get(".emptyDir.sizeLimit", tmpfs_vol)

    def _iter_containers(self):
        yield self._agent_container
        yield self._sandbox_container

    def _spec_init(self):
        self._spec_init_labels()
        self._spec_init_containers()
        self._spec_init_tmpfs_volume()
        self._spec_init_node_selector()
        self._spec_init_tolerations()

        for container in self._iter_containers():
            self._spec_init_rs_requests(container)
            self._spec_init_rs_limits(container)
            self._spec_init_env(container)

    def __init__(self, template_file: str):

        try:
            self._root = spec_load(template_file)
            self._spec_init()

        except SpecLoadError as e:
            raise AgentSpecLoadError(str(e)) from e

        except SpecParseError as e:
            raise AgentSpecParseError(str(e)) from e

    def copy(self) -> AgentSpec:
        return AgentSpec(deepcopy(self._root))
