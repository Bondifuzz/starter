from ..base.errors import SpecValidationError
from ..base.spec import spec_validate
from .errors import AgentSpecValidationError


class AgentSpec:

    _root: dict
    _labels: dict
    _agent_container: dict
    _sandbox_container: dict
    _tolerations: list

    def __init__(self, agent_body: dict):
        containers = agent_body["spec"]["containers"]
        containers_kv = {c["name"]: c for c in containers}
        self._agent_container = containers_kv["agent"]
        self._sandbox_container = containers_kv["sandbox"]
        self._tolerations = agent_body["spec"]["tolerations"]
        self._labels = agent_body["metadata"]["labels"]
        self._vol_list = agent_body["spec"]["volumes"]
        self._root = agent_body

    def validate(self):
        try:
            spec_validate(self._root, "$root")
        except SpecValidationError as e:
            raise AgentSpecValidationError(str(e)) from e

    def as_dict(self) -> dict:

        if __debug__:
            self.validate()

        return self._root

    def set_tmpfs_size(self, size: str):
        vol = next(filter(lambda v: v["name"] == "tmpfs", self._vol_list))
        vol["emptyDir"]["sizeLimit"] = size

    def _set_env(self, name: str, value: str, container: str):

        env = {
            "name": name,
            "value": value,
        }

        env_list: list = container["env"]

        def name_equal(env: dict):
            return env["name"] == name

        try:
            res: dict = next(filter(name_equal, env_list))
            res.update(env)

        except StopIteration:
            env_list.append(env)

    def set_label(self, name: str, value: str):
        self._labels[name] = value

    def set_grace_period(self, seconds: int):
        self._root["spec"]["terminationGracePeriodSeconds"] = seconds

    def set_deadline_seconds(self, seconds: int):
        self._root["spec"]["activeDeadlineSeconds"] = seconds

    def set_node_selector(self, key: str, value: str):
        self._root["spec"]["nodeSelector"][key] = value

    def set_toleration(
        self,
        key: str,
        value: str,
        operator: str,
        effect: str,
    ):
        tlr = {
            "key": key,
            "value": value,
            "operator": operator,
            "effect": effect,
        }

        def name_exists(tlr: str):
            return tlr["key"] == key

        try:
            res: dict = next(filter(name_exists, self._tolerations))
            res.update(tlr)

        except StopIteration:
            self._tolerations.append(tlr)

    def set_agent_image_name(self, image_name: str):
        self._agent_container["image"] = image_name
        return self

    def set_agent_command(self, cmd: str):
        self._agent_container["command"] = ["sh", "-c", cmd]

    def set_agent_env(self, name: str, value: str):
        return self._set_env(name, value, self._agent_container)

    def set_agent_rs_requests(self, cpu: str, ram: str):
        rs = {"cpu": cpu, "memory": ram}
        self._agent_container["resources"]["requests"] = rs

    def set_agent_rs_limits(self, cpu: str, ram: str):
        rs = {"cpu": cpu, "memory": ram}
        self._agent_container["resources"]["limits"] = rs

    def set_sandbox_image_name(self, image_name: str):
        self._sandbox_container["image"] = image_name

    def set_sandbox_command(self, cmd: str):
        self._sandbox_container["command"] = ["sh", "-c", cmd]

    def set_sandbox_env(self, name: str, value: str):
        self._set_env(name, value, self._sandbox_container)

    def set_sandbox_rs_requests(self, cpu: str, ram: str):
        rs = {"cpu": cpu, "memory": ram}
        self._sandbox_container["resources"]["requests"] = rs

    def set_sandbox_rs_limits(self, cpu: str, ram: str):
        rs = {"cpu": cpu, "memory": ram}
        self._sandbox_container["resources"]["limits"] = rs
