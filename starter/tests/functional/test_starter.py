from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import pytest

from starter.app.agent import AgentSpecTemplate
from starter.app.kubernetes.client import KubernetesClient
from starter.app.settings import AppSettings

from .conftest import FuzzerData, random_string, waits_for_events

if TYPE_CHECKING:
    from .message_queue import MQApp, MQAppState


@pytest.mark.asyncio
@waits_for_events
async def test_k8s_listener_normal(
    mq_app: MQApp,
    k8s_client: KubernetesClient,
    template: AgentSpecTemplate,
    fuzzer_data: FuzzerData,
):
    """
    Description:
        Created agent pod which exits normally

    Succeeds:
        If event is catched and agent result is not empty
    """

    tm_sec = 10
    state: MQAppState = mq_app.state
    mc_fuzzer_finished = state.consumers.st_fuzzer_finished

    agent_spec = template.copy()
    agent_spec.set_deadline_seconds(tm_sec)
    agent_spec.set_label("fuzzer_id", fuzzer_data.id)
    agent_spec.set_label("fuzzer_rev", fuzzer_data.rev)
    agent_spec.set_label("agent_mode", fuzzer_data.mode)
    agent_spec.set_label("fuzzer_engine", fuzzer_data.engine)
    agent_spec.set_label("fuzzer_lang", fuzzer_data.lang)
    agent_spec.set_container_name(fuzzer_data.container)
    agent_spec.set_image_name(fuzzer_data.image)
    body = agent_spec.as_dict()

    await k8s_client.create_pod(body)
    event = await mc_fuzzer_finished.get_next_event(timeout=tm_sec)

    assert event.fuzzer_id == fuzzer_data.id
    assert event.fuzzer_rev == fuzzer_data.rev
    assert event.agent_result == {"a": "b"}


@pytest.mark.asyncio
async def test_k8s_listener_err_agent_failed(
    mq_app: MQApp,
    k8s_client: KubernetesClient,
    template: AgentSpecTemplate,
    fuzzer_data: FuzzerData,
):
    """
    Description:
        Created agent pod which exits with error

    Succeeds:
        If event is catched and agent result is empty
    """

    tm_sec = 10
    state: MQAppState = mq_app.state
    mc_fuzzer_finished = state.consumers.st_fuzzer_finished

    agent_spec = template.copy()
    agent_spec.set_deadline_seconds(tm_sec)
    agent_spec.set_label("fuzzer_id", fuzzer_data.id)
    agent_spec.set_label("fuzzer_rev", fuzzer_data.rev)
    agent_spec.set_label("agent_mode", fuzzer_data.mode)
    agent_spec.set_label("fuzzer_engine", fuzzer_data.engine)
    agent_spec.set_label("fuzzer_lang", fuzzer_data.lang)
    agent_spec.set_container_name(fuzzer_data.container)
    agent_spec.set_image_name(fuzzer_data.image)
    agent_spec.set_command("cat no-such-file.txt")
    body = agent_spec.as_dict()

    await k8s_client.create_pod(body)
    event = await mc_fuzzer_finished.get_next_event(timeout=tm_sec)

    assert event.fuzzer_id == fuzzer_data.id
    assert event.fuzzer_rev == fuzzer_data.rev
    assert event.agent_result is None


@pytest.mark.asyncio
async def test_k8s_listener_err_deadline_exceeded(
    mq_app: MQApp,
    k8s_client: KubernetesClient,
    template: AgentSpecTemplate,
    fuzzer_data: FuzzerData,
):
    """
    Description:
        Launches pod which will run too long

    Succeeds:
        If dangling pod was killed after its ttl expiration
        and that event will be catched
    """

    state: MQAppState = mq_app.state
    mc_fuzzer_finished = state.consumers.st_fuzzer_finished

    agent_spec = template.copy()
    agent_spec.set_deadline_seconds(5)
    agent_spec.set_label("fuzzer_id", fuzzer_data.id)
    agent_spec.set_label("fuzzer_rev", fuzzer_data.rev)
    agent_spec.set_label("agent_mode", fuzzer_data.mode)
    agent_spec.set_label("fuzzer_engine", fuzzer_data.engine)
    agent_spec.set_label("fuzzer_lang", fuzzer_data.lang)
    agent_spec.set_container_name(fuzzer_data.container)
    agent_spec.set_image_name(fuzzer_data.image)
    agent_spec.set_command("sleep 20")
    body = agent_spec.as_dict()

    await k8s_client.create_pod(body)
    event = await mc_fuzzer_finished.get_next_event(timeout=10)

    assert event.fuzzer_id == fuzzer_data.id
    assert event.fuzzer_rev == fuzzer_data.rev
    assert event.agent_result is None


@pytest.mark.asyncio
async def test_k8s_listener_err_oom_killed(
    mq_app: MQApp,
    k8s_client: KubernetesClient,
    template: AgentSpecTemplate,
    fuzzer_data: FuzzerData,
):
    """
    Description:
        Launches pod which will exceed all RAM

    Succeeds:
        If pod will be killed and that event will be catched
    """

    tm_sec = 60
    state: MQAppState = mq_app.state
    mc_fuzzer_finished = state.consumers.st_fuzzer_finished

    agent_spec = template.copy()
    agent_spec.set_deadline_seconds(tm_sec)
    agent_spec.set_image_name(fuzzer_data.image)
    agent_spec.set_label("fuzzer_id", fuzzer_data.id)
    agent_spec.set_label("fuzzer_rev", fuzzer_data.rev)
    agent_spec.set_label("agent_mode", fuzzer_data.mode)
    agent_spec.set_label("fuzzer_engine", fuzzer_data.engine)
    agent_spec.set_label("fuzzer_lang", fuzzer_data.lang)
    agent_spec.set_container_name(fuzzer_data.container)
    agent_spec.set_command("cat /dev/zero | head -c 500m | tail")
    body = agent_spec.as_dict()

    await k8s_client.create_pod(body)
    event = await mc_fuzzer_finished.get_next_event(timeout=tm_sec)

    assert event.fuzzer_id == fuzzer_data.id
    assert event.fuzzer_rev == fuzzer_data.rev
    assert event.agent_result is None


@pytest.mark.asyncio
async def test_k8s_listener_err_evicted(
    mq_app: MQApp,
    k8s_client: KubernetesClient,
    template: AgentSpecTemplate,
    fuzzer_data: FuzzerData,
):
    """
    Description:
        Launches pod which will exceed all disk space

    Succeeds:
        If pod will be killed and that event will be catched
    """

    tm_sec = 120
    state: MQAppState = mq_app.state
    mc_fuzzer_finished = state.consumers.st_fuzzer_finished
    cmd = f"dd if=/dev/zero of=/mnt/disk/file bs=1M count=100; sleep {tm_sec}"

    agent_spec = template.copy()
    agent_spec.set_deadline_seconds(tm_sec)
    agent_spec.set_label("fuzzer_id", fuzzer_data.id)
    agent_spec.set_label("fuzzer_rev", fuzzer_data.rev)
    agent_spec.set_label("agent_mode", fuzzer_data.mode)
    agent_spec.set_label("fuzzer_engine", fuzzer_data.engine)
    agent_spec.set_label("fuzzer_lang", fuzzer_data.lang)
    agent_spec.set_container_name(fuzzer_data.container)
    agent_spec.set_image_name(fuzzer_data.image)
    agent_spec.set_command(cmd)
    body = agent_spec.as_dict()

    await k8s_client.create_pod(body)
    event = await mc_fuzzer_finished.get_next_event(timeout=tm_sec)

    assert event.fuzzer_id == fuzzer_data.id
    assert event.fuzzer_rev == fuzzer_data.rev
    assert event.agent_result is None


@pytest.mark.asyncio
async def test_k8s_listener_not_fuzzer_pod(
    mq_app: MQApp,
    k8s_client: KubernetesClient,
    template: AgentSpecTemplate,
    fuzzer_data: FuzzerData,
):
    """
    Description:
        Launches pod which is not fuzzer

    Succeeds:
        If pod will not be touched
    """

    tm_sec = 10
    state: MQAppState = mq_app.state

    agent_spec = template.copy()
    agent_spec.set_deadline_seconds(tm_sec)
    agent_spec.set_container_name(fuzzer_data.container)
    agent_spec.set_image_name(fuzzer_data.image)
    body = agent_spec.as_dict()

    await k8s_client.create_pod(body)

    with pytest.raises(asyncio.TimeoutError):
        await state.consumers.st_fuzzer_finished.get_next_event(timeout=tm_sec)


@pytest.mark.parametrize("n", [1, 2, 5])
@pytest.mark.asyncio
@waits_for_events
async def test_run_fuzzer(mq_app: MQApp, n: int, settings: AppSettings):

    """
    Description:
        Creates a task to run fuzzer N times.
        All tasks must finish normally.

    Succeeds:
        If all events are catched and results are not empty
    """

    fuzzer_ids = list()
    fuzzer_revs = list()
    state: MQAppState = mq_app.state
    mc_fuzzer_finished = state.consumers.st_fuzzer_finished
    mp_fuzzer_run = state.producers.sch_fuzzer_run

    for _ in range(n):
        fuzzer = FuzzerData(settings)
        fuzzer_ids.append(fuzzer.id)
        fuzzer_revs.append(fuzzer.rev)
        await mp_fuzzer_run.produce(**fuzzer.to_dict())

    for _ in range(n):
        event = await mc_fuzzer_finished.get_next_event(timeout=20)
        assert event.fuzzer_id in fuzzer_ids
        assert event.fuzzer_rev in fuzzer_revs
        assert event.agent_result == {"a": "b"}


@pytest.mark.asyncio
async def test_cluster_scaled(mq_app: MQApp):
    """
    Description:
        Check that starter sends messages
        with cluster resources in total

    Succeeds:
        If message was received
    """
    state: MQAppState = mq_app.state
    mc_cluster_info = state.consumers.st_cluster_scaled
    await mc_cluster_info.get_next_event(timeout=40)


@pytest.mark.asyncio
async def test_resource_sync(mq_app: MQApp):
    """
    Description:
        Handles resources sync operation from scheduler

    Succeeds:
        If response was sent and no errors occurred
    """

    tm_sec = 60
    state: MQAppState = mq_app.state
    mc_resource_sync = state.consumers.st_resource_sync
    mp_resource_sync = state.producers.sch_resource_sync

    session_id = random_string(12)
    await mp_resource_sync.produce(session_id=session_id)
    event = await mc_resource_sync.get_next_event(timeout=tm_sec)

    assert event.session_id == session_id
    assert event.cpu_total >= 0
    assert event.ram_total >= 0
    assert event.cpu_used >= 0
    assert event.ram_used >= 0
