from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import DefaultDict, Dict, Optional

from .errors import PodAlreadyExistsError, PodNotFoundError


@dataclass
class FuzzerPod:

    # V1Pod
    name: str
    phase: str
    start_time: Optional[datetime]
    displaced: bool
    deleting: bool
    cpu: int
    ram: int

    # Suitcase
    user_id: str
    project_id: str
    pool_id: str
    fuzzer_id: str
    fuzzer_rev: str
    agent_mode: str
    fuzzer_lang: str
    fuzzer_engine: str
    session_id: str

    # Pre-saved logs
    agent_logs: Optional[str]
    sandbox_logs: Optional[str]
    logs_saved: bool

    def as_dict(self):
        return asdict(self)


class FuzzerPodRegistry:

    _pods: Dict[str, FuzzerPod]
    _dsp_pools: DefaultDict[str, int]

    def __init__(self) -> None:
        self._dsp_pools = defaultdict(int)
        self._pods = {}

    def add_pod(self, pod: FuzzerPod):

        if pod.name in self._pods:
            raise PodAlreadyExistsError(pod.name)

        self._pods[pod.name] = pod

        if pod.displaced:
            self._dsp_pools[pod.pool_id] += 1

    def remove_pod(self, pod_name: str):
        try:
            pod = self._pods.pop(pod_name)
        except KeyError as e:
            msg = f"Pod '{pod_name}' not found"
            raise PodNotFoundError(msg) from e

        if pod.displaced:
            self._dsp_pools[pod.pool_id] -= 1

    def find_pod(self, pod_name: str):

        try:
            res = self._pods[pod_name]
        except KeyError as e:
            msg = f"Pod '{pod_name}' not found"
            raise PodNotFoundError(msg) from e

        return res

    def displace_pod(self, pod_name: str):
        pod = self.find_pod(pod_name)
        self._dsp_pools[pod.pool_id] += 1
        pod.displaced = True

    def list_pods(self):
        return list(self._pods.values())

    def has_pod(self, pod_name: str):
        return self._pods.get(pod_name) is not None

    def displacement_in_progress(self, pool_id: str):
        return self._dsp_pools[pool_id] > 0
