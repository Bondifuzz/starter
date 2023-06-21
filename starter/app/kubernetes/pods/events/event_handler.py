from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, List

from kubernetes_asyncio.client import ApiException

from starter.app.database.orm import ORMLaunch
from starter.app.kubernetes.pods.registry.errors import PodNotFoundError
from starter.app.kubernetes.pods.registry.pod_registry import (
    FuzzerPod,
    FuzzerPodRegistry,
)
from starter.app.kubernetes.pools.registry import PoolRegistry
from starter.app.settings import AppSettings, PodOutputSaveMode
from starter.app.util.datetime import date_future, date_now, rfc3339

if TYPE_CHECKING:

    from mqtransport import MQApp

    # fmt: off
    # isort: off
    from kubernetes_asyncio.client.models.v1_pod import V1Pod
    from kubernetes_asyncio.client.models.v1_container_state import V1ContainerState
    from kubernetes_asyncio.client.models.v1_container_state_terminated import V1ContainerStateTerminated
    from kubernetes_asyncio.client.models.v1_container_status import V1ContainerStatus
    from kubernetes_asyncio.client.models.v1_object_meta import V1ObjectMeta
    from kubernetes_asyncio.client.models.v1_pod_status import V1PodStatus
    # isort: on
    # fmt: on

    from starter.app.database.abstract import IDatabase
    from starter.app.kubernetes.client import KubernetesClient
    from starter.app.message_queue import MQAppState


@dataclass
class ContainerExitInfo:
    start_time: datetime
    finish_time: datetime
    exit_code: int
    reason: str


class NotTerminatedError(Exception):
    pass


class FuzzerPodStateChecker:

    _agent_state: V1ContainerState
    _sandbox_state: V1ContainerState

    def __init__(self, pod: V1Pod):

        status: V1PodStatus = pod.status
        statuses: List[V1ContainerStatus] = status.container_statuses
        statuses_kv = {status.name: status for status in statuses}

        agent_status = statuses_kv["agent"]
        self._agent_state = agent_status.state

        sandbox_status = statuses_kv["sandbox"]
        self._sandbox_state = sandbox_status.state

    @staticmethod
    def _termination_info(state: V1ContainerState):

        if not state.terminated:
            raise NotTerminatedError("Container is not terminated")

        terminated: V1ContainerStateTerminated = state.terminated

        return ContainerExitInfo(
            start_time=terminated.started_at,
            finish_time=terminated.finished_at,
            exit_code=terminated.exit_code,
            reason=terminated.reason,
        )

    def agent_termination_info(self):
        return self._termination_info(self._agent_state)

    def sandbox_termination_info(self):
        return self._termination_info(self._sandbox_state)

    def is_agent_terminated(self):
        return self._agent_state.terminated is not None

    def is_agent_terminated(self):
        return self._agent_state.terminated is not None

    def is_sandbox_terminated(self):
        return self._agent_state.terminated is not None


class PodEventHandler:

    _mq: MQApp
    _db: IDatabase
    _k8s: KubernetesClient
    _output_save_mode: PodOutputSaveMode
    _saved_info_exp_seconds: int

    def __init__(
        self,
        mq_app: MQApp,
        db: IDatabase,
        pool_registry: PoolRegistry,
        pod_registry: FuzzerPodRegistry,
        k8s_client: KubernetesClient,
        settings: AppSettings,
    ):
        self._logger = logging.getLogger("k8s.events")
        self._output_save_mode = settings.fuzzer_pod.output_save_mode
        self._saved_info_exp_seconds = settings.fuzzer_pod.launch_info_retention_period
        self._pod_min_work_time = settings.fuzzer_pod.min_work_time
        self._pool_registry = pool_registry
        self._pod_registry = pod_registry
        self._k8s = k8s_client
        self._mq = mq_app
        self._db = db

    async def _read_log(self, pod_name: str, container_name: str):

        logs = None

        try:
            logs = await self._k8s.read_pod_log(pod_name, container_name)

        except ApiException as e:
            if e.status == 400:
                msg = "Failed to retrieve logs of <pod='%s', container='%s'. Inaccessible"  # fmt: skip
                self._logger.warning(msg, pod_name, container_name)
            elif e.status == 404:
                msg = "Failed to retrieve logs of <pod='%s', container='%s'. Pod not found"  # fmt: skip
                self._logger.warning(msg, pod_name, container_name)
            else:
                msg = "Failed to retrieve logs of <pod='%s', container='%s'. Reason - %s"  # fmt: skip
                self._logger.error(msg, pod_name, container_name, e)

        return logs

    async def _notify_fuzzer_pod_finished(self, pod: FuzzerPod, success: bool):

        state: MQAppState = self._mq.state
        producer = state.producers.sch_pod_finished

        await producer.produce(
            # Suitcase
            user_id=pod.user_id,
            project_id=pod.project_id,
            pool_id=pod.pool_id,
            fuzzer_id=pod.fuzzer_id,
            fuzzer_rev=pod.fuzzer_rev,
            agent_mode=pod.agent_mode,
            fuzzer_lang=pod.fuzzer_lang,
            fuzzer_engine=pod.fuzzer_engine,
            session_id=pod.session_id,
            # Other
            success=success,
        )

    async def _save_pod_launch_to_db(
        self, pod: FuzzerPod, term_info: ContainerExitInfo
    ):
        save_mode = self._output_save_mode
        if save_mode == PodOutputSaveMode.none:
            return

        if save_mode == PodOutputSaveMode.err and term_info.exit_code == 0:
            return

        exp_seconds = self._saved_info_exp_seconds
        exp_date = date_future(term_info.start_time, exp_seconds)

        await self._db.launches.save(
            ORMLaunch(
                # Suitcase
                fuzzer_id=pod.fuzzer_id,
                fuzzer_rev=pod.fuzzer_rev,
                fuzzer_engine=pod.fuzzer_engine,
                agent_mode=pod.agent_mode,
                fuzzer_lang=pod.fuzzer_lang,
                session_id=pod.session_id,
                project_id=pod.project_id,
                user_id=pod.user_id,
                # V1Pod
                start_time=rfc3339(term_info.start_time),
                finish_time=rfc3339(term_info.finish_time),
                exit_reason=term_info.reason,
                agent_logs=pod.agent_logs,
                sandbox_logs=pod.sandbox_logs,
                exp_date=rfc3339(exp_date),
            )
        )

    def _remove_pod_from_registry_and_free_resources(self, pod: FuzzerPod):
        self._pool_registry.free_resources(pod.pool_id, pod.cpu, pod.ram)
        self._pod_registry.remove_pod(pod.name)

    async def _handle_fuzzer_pod_deletion(self, pod: FuzzerPod, success: bool):
        self._remove_pod_from_registry_and_free_resources(pod)
        await self._notify_fuzzer_pod_finished(pod, success)

    async def _delete_pod_safe(self, pod_name: str):
        try:
            await self._k8s.delete_fuzzer_pod(pod_name)
        except ApiException as e:
            msg = "Failed to delete pod '%s'. Reason - %s"
            self._logger.error(msg, pod_name, str(e))

    @staticmethod
    def _pod_info_str(pod: FuzzerPod):
        return "<id='%s', rev='%s', mode='%s', pod='%s'>" % (
            pod.fuzzer_id, pod.fuzzer_rev, pod.agent_mode, pod.name  # fmt: skip
        )

    async def _delete_displaced_pod(self, pod: FuzzerPod):

        assert pod.start_time is not None
        assert pod.displaced

        now = date_now()
        min_work_time = timedelta(seconds=self._pod_min_work_time)

        # Candidate has been running long enough -> can be deleted now
        if now > pod.start_time + min_work_time:
            msg = "Fuzzer %s will be deleted now"
            self._logger.debug(msg, self._pod_info_str(pod))
            await self._delete_pod_safe(pod.name)
            return

        # Candidate hasn't been working long enough -> can be deleted only after delay
        async def delete_pod_after_delay(delay_seconds: int):
            await asyncio.sleep(delay_seconds)
            await self._delete_pod_safe(pod.name)

        # XXX: Sometimes pod.start_date can be greater than date_now()
        # So, delay can be longer than expected. This is not a bug
        delay = min_work_time - (now - pod.start_time)

        msg = "Fuzzer %s will be deleted after %s seconds"
        self._logger.debug(msg, self._pod_info_str(pod), delay.seconds)

        loop = asyncio.get_running_loop()
        loop.create_task(delete_pod_after_delay(delay.seconds))

    async def _save_pod_logs(self, pod: FuzzerPod):

        if pod.logs_saved:
            return

        agent_logs, sandbox_logs = await asyncio.gather(
            self._read_log(pod.name, "agent"),
            self._read_log(pod.name, "sandbox"),
        )

        pod.agent_logs = agent_logs
        pod.sandbox_logs = sandbox_logs
        pod.logs_saved = True

    async def handle(self, event_type: str, v1_pod: V1Pod):

        #
        # Find pod in registry and refresh its state
        # If pod is not in registry, ignore this pod event
        #

        v1_status: V1PodStatus = v1_pod.status
        v1_meta: V1ObjectMeta = v1_pod.metadata
        pod_name: str = v1_meta.name

        try:
            pod = self._pod_registry.find_pod(pod_name)
        except PodNotFoundError:
            return

        if pod.start_time is None:
            if v1_status.start_time is not None:
                msg = "Fuzzer %s is now running"
                self._logger.info(msg, self._pod_info_str(pod))
                pod.start_time = v1_status.start_time

        pod.phase = v1_status.phase

        #
        # Handle case when pod is being deleted (e.g. 'kubectl delete pod' command)
        # Unfortunately, it's impossible to save pod logs after it gets deleted.
        # So logs must be saved when pod termination is in progress (graceful shutdown)
        # The start of pod termination is tracked by deletionTimstamp field in pod spec.
        #

        if v1_meta.deletion_timestamp and not pod.deleting:
            msg = "Fuzzer %s is terminating (graceful shutdown)"
            self._logger.info(msg, self._pod_info_str(pod))
            await self._save_pod_logs(pod)
            pod.deleting = True

        #
        # Pod marked for deletion, but has not been
        # deleted for some reason. Call API to delete it
        #

        if pod.displaced and not pod.deleting:
            msg = "Fuzzer %s is marked for deletion"
            self._logger.info(msg, self._pod_info_str(pod))
            await self._delete_displaced_pod(pod)
            return

        #
        # Handle special cases when we need to free pool resources
        #

        if event_type == "DELETED" and pod.phase == "Pending":
            msg = "Fuzzer %s could not start and is now deleted"
            self._logger.info(msg, self._pod_info_str(pod))
            await self._handle_fuzzer_pod_deletion(pod, success=False)
            return

        if event_type == "DELETED" and pod.phase == "Running":
            msg = "Fuzzer %s is lost (k8s node is no more available)"
            self._logger.info(msg, self._pod_info_str(pod))
            await self._handle_fuzzer_pod_deletion(pod, success=False)
            return

        if pod.phase in ["Pending", "Unknown"]:
            return

        #
        # Handle pod deletion:
        #   - free pool resources
        #   - save launch info to database
        #   - notify scheduler
        #

        checker = FuzzerPodStateChecker(v1_pod)

        if event_type == "DELETED":
            try:
                msg = "Fuzzer %s deleted. Handling..."
                self._logger.info(msg, self._pod_info_str(pod))

                term_info = checker.agent_termination_info()
                await self._handle_fuzzer_pod_deletion(pod, term_info.exit_code == 0)
                await self._save_pod_launch_to_db(pod, term_info)

                msg = "Fuzzer %s deleted. Handling... OK"
                self._logger.info(msg, self._pod_info_str(pod))

            except NotTerminatedError:
                reason = "Agent container is not terminated"
                msg = "Fuzzer %s deleted. Handling... Failed. Reason - %s"
                self._logger.error(msg, self._pod_info_str(pod), reason)
                await self._handle_fuzzer_pod_deletion(pod, success=False)

            except Exception as e:
                msg = "Fuzzer %s deleted. Handling... Failed. Reason - %s"
                self._logger.error(msg, self._pod_info_str(pod), str(e))
                await self._handle_fuzzer_pod_deletion(pod, success=False)

            return

        #
        # If agent exited (container terminated), delete the pod
        #

        if checker.is_agent_terminated() and not pod.deleting:
            msg = "Fuzzer %s exited. Call API to delete the pod"
            self._logger.info(msg, self._pod_info_str(pod))
            await self._delete_pod_safe(pod.name)
            return
