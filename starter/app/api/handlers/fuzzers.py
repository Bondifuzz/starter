import asyncio
from dataclasses import dataclass
from typing import Any

from fastapi import APIRouter, Depends, Path, Response
from pydantic import BaseModel, ConstrainedInt, ConstrainedStr
from starlette.status import *

from starter.app.kubernetes.client import KubernetesClient
from starter.app.kubernetes.pods.displacement import try_displace_pods
from starter.app.kubernetes.pods.registry import FuzzerPod, FuzzerPodRegistry
from starter.app.kubernetes.pools.registry import PoolRegistry
from starter.app.kubernetes.pools.registry.errors import (
    PoolCapacityExceededError,
    PoolLockedError,
    PoolNoResourcesLeftError,
    PoolNotFoundError,
    PoolOverflowError,
)
from starter.app.settings import AppSettings
from starter.app.util.images import agent_image_name, sandbox_image_name

from ..base import ResponseModelFailed, ResponseModelOk
from ..depends import (
    Operation,
    get_k8s_client,
    get_pod_registry,
    get_pool_registry,
    get_settings,
)
from ..error_codes import *
from ..error_model import error_model, error_msg
from ..utils import (
    log_operation_debug_info_to,
    log_operation_error_to,
    log_operation_success_to,
)

router = APIRouter(
    prefix="/pools/{pool_id}/fuzzers",
    tags=["fuzzers"],
)


def log_operation_debug_info(operation: str, info: Any):
    log_operation_debug_info_to("api.fuzzers", operation, info)


def log_operation_success(operation: str, **kwargs):
    log_operation_success_to("api.fuzzers", operation, **kwargs)


def log_operation_error(operation: str, reason: str, **kwargs):
    log_operation_error_to("api.fuzzers", operation, reason, **kwargs)


########################################
# Run fuzzer
########################################


class LimitedString(ConstrainedStr):
    min_length = 1
    max_length = 64


class ResourceUsage(ConstrainedInt):
    gt = 0


@dataclass
class ComputeResources:
    cpu: int
    ram: int


class RunFuzzerRequestModel(BaseModel):

    ##################################################
    # Variables which are "in-transit"
    ##################################################

    user_id: LimitedString
    """ User ID. This variable is 'in-transit', used by other services """

    project_id: LimitedString
    """ Project ID. This variable is 'in-transit', used by other services """

    #
    # Scheduler implements a `restart` command which allows to replace
    # the faulty fuzzer with working one. Then scheduler resets the fuzzer
    # state and starts its new instances (k8s pods, this service). However,
    # even after a user applies this command, inoperable instances with old
    # fuzzer binaries may still have been running. When Scheduler handles
    # the results of such instance, it treats this as an error and stops the
    # fuzzer, which is wrong. So, this variable is used to distinguish old
    # instances from the new ones and prevent the errors described above.
    #

    session_id: LimitedString
    """ Fuzzer session ID. This variable is 'in-transit', used by other services """

    ##################################################
    # Variables which are required for fuzzer pod launch
    ##################################################

    fuzzer_id: LimitedString
    """ Fuzzer ID """

    fuzzer_rev: LimitedString
    """ Fuzzer revision """

    fuzzer_engine: LimitedString
    """ Fuzzer engine: AFL, LibFuzzer, Atheris, etc... """

    fuzzer_lang: LimitedString
    """ Programming language: Cpp, Python, Java, etc... """

    agent_mode: LimitedString
    """ Fuzzer mode: fuzzing, merge or firstrun """

    image_id: LimitedString
    """ (ID) Sandbox image where fuzzer will be run"""

    cpu_usage: ResourceUsage
    """ Fuzzer CPU usage in mcpu """

    ram_usage: ResourceUsage
    """ Fuzzer RAM usage in MiB """

    tmpfs_size: ResourceUsage
    """ Fuzzer tmpfs size in MiB """


@router.post(
    path="",
    status_code=HTTP_201_CREATED,
    responses={
        HTTP_201_CREATED: {
            "model": ResponseModelOk,
            "description": "Successful response",
        },
        HTTP_404_NOT_FOUND: {
            "model": ResponseModelFailed,
            "description": error_msg(E_POOL_NOT_FOUND),
        },
        HTTP_409_CONFLICT: {
            "model": ResponseModelFailed,
            "description": error_msg(E_POOL_TOO_SMALL, E_POOL_NO_RESOURCES),
        },
    },
)
async def run_fuzzer(
    response: Response,
    launch: RunFuzzerRequestModel,
    pool_id: LimitedString = Path(...),
    operation: str = Depends(Operation("Run fuzzer")),
    pool_registry: PoolRegistry = Depends(get_pool_registry),
    pod_registry: FuzzerPodRegistry = Depends(get_pod_registry),
    k8s_client: KubernetesClient = Depends(get_k8s_client),
    settings: AppSettings = Depends(get_settings),
):
    def error_response(status_code: int, error_code: int):
        kw = {"fuzzer_id": launch.fuzzer_id, "fuzzer_rev": launch.fuzzer_rev}
        rfail = ResponseModelFailed.construct(error=error_model(error_code))
        log_operation_error(operation, rfail.error, **kw)
        response.status_code = status_code
        return rfail

    log_operation_debug_info(operation, launch)

    #
    # Total ram usage of the container
    # includes its files stored in tmpfs
    #

    rs_sandbox = ComputeResources(
        launch.cpu_usage,
        launch.ram_usage + launch.tmpfs_size,
    )

    rs_agent = ComputeResources(
        settings.fuzzer_pod.agent_cpu,
        settings.fuzzer_pod.agent_ram,
    )

    rs_total = ComputeResources(
        rs_sandbox.cpu + rs_agent.cpu,
        rs_sandbox.ram + rs_agent.ram,
    )

    #
    # First, try to allocate resources for pod from resource pool
    # If resources have been allocated, create pod
    #

    try:
        pool_registry.allocate_resources(pool_id, rs_total.cpu, rs_total.ram)
    except PoolNotFoundError:
        return error_response(HTTP_404_NOT_FOUND, E_POOL_NOT_FOUND)

    except PoolLockedError:
        return error_response(HTTP_409_CONFLICT, E_POOL_LOCKED)

    except PoolCapacityExceededError:
        return error_response(HTTP_409_CONFLICT, E_POOL_TOO_SMALL)

    except (PoolNoResourcesLeftError, PoolOverflowError):

        #
        # Mode "firstrun" has the highest priority to run,
        # because user wants to see first fuzzing results immediately.
        # So, pods with lower priority should be stopped to free resources
        #

        if launch.agent_mode == "firstrun":
            if not pod_registry.displacement_in_progress(pool_id):
                free_cpu, free_ram = pool_registry.resources_left(pool_id)
                cpu_required = rs_total.cpu - free_cpu
                ram_required = rs_total.ram - free_ram

                asyncio.get_running_loop().create_task(
                    try_displace_pods(
                        pool_id,
                        pod_registry,
                        k8s_client,
                        cpu_required,
                        ram_required,
                    )
                )

        return error_response(HTTP_409_CONFLICT, E_POOL_NO_RESOURCES)

    #
    # Try to create pod using kubernetes API
    # If operation failed, free allocated resources
    #

    agent_image = agent_image_name(launch.fuzzer_engine, settings)
    sandbox_image = sandbox_image_name(launch.image_id, settings)

    try:
        pod = await k8s_client.create_fuzzer_pod(
            user_id=launch.user_id,
            project_id=launch.project_id,
            pool_id=pool_id,
            fuzzer_id=launch.fuzzer_id,
            fuzzer_rev=launch.fuzzer_rev,
            agent_mode=launch.agent_mode,
            fuzzer_lang=launch.fuzzer_lang,
            fuzzer_engine=launch.fuzzer_engine,
            session_id=launch.session_id,
            agent_image=agent_image,
            sandbox_image=sandbox_image,
            agent_cpu_usage=rs_agent.cpu,
            agent_ram_usage=rs_agent.ram,
            sandbox_cpu_usage=rs_sandbox.cpu,
            sandbox_ram_usage=rs_sandbox.ram,
            tmpfs_size=launch.tmpfs_size,
        )

    except:
        pool_registry.free_resources(pool_id, rs_total.cpu, rs_total.ram)
        raise

    pod_registry.add_pod(
        FuzzerPod(
            # V1Pod
            name=pod.metadata.name,
            phase=pod.status.phase,
            displaced=False,
            deleting=False,
            cpu=rs_total.cpu,
            ram=rs_total.ram,
            start_time=None,
            # Suitcase
            user_id=launch.user_id,
            project_id=launch.project_id,
            pool_id=pool_id,
            fuzzer_id=launch.fuzzer_id,
            fuzzer_rev=launch.fuzzer_rev,
            agent_mode=launch.agent_mode,
            fuzzer_lang=launch.fuzzer_lang,
            fuzzer_engine=launch.fuzzer_engine,
            session_id=launch.session_id,
            # Pre saved logs
            agent_logs=None,
            sandbox_logs=None,
            logs_saved=False,
        )
    )

    log_operation_success(
        operation=operation,
        pool_id=pool_id,
        fuzzer_id=launch.fuzzer_id,
        fuzzer_rev=launch.fuzzer_rev,
        agent_mode=launch.agent_mode,
    )

    return ResponseModelOk()


########################################
# Stop fuzzer pods in pool
########################################


@router.delete(
    path="/{fuzzer_id}",
    status_code=HTTP_200_OK,
    responses={
        HTTP_200_OK: {
            "model": ResponseModelOk,
            "description": "Successful response",
        },
    },
)
async def stop_fuzzer_pods(
    operation: str = Depends(Operation("Stop fuzzer pods")),
    k8s_client: KubernetesClient = Depends(get_k8s_client),
    fuzzer_id: str = Path(..., regex=r"^\d+$"),
    pool_id: str = Path(...),
):
    await k8s_client.delete_fuzzer_pods(
        fuzzer_id=fuzzer_id,
        pool_id=pool_id,
    )

    log_operation_success(
        operation,
        pool_id=pool_id,
        fuzzer_id=fuzzer_id,
    )

    return ResponseModelOk()


########################################
# Stop all fuzzer pods in pool
########################################


@router.delete(
    path="",
    status_code=HTTP_200_OK,
    responses={
        HTTP_200_OK: {
            "model": ResponseModelOk,
            "description": "Successful response",
        },
    },
)
async def stop_all_fuzzer_pods(
    operation: str = Depends(Operation("Stop all fuzzer pods")),
    k8s_client: KubernetesClient = Depends(get_k8s_client),
    pool_id: str = Path(...),
):

    await k8s_client.delete_fuzzer_pods(
        pool_id=pool_id,
    )

    log_operation_success(
        operation,
        pool_id=pool_id,
    )

    return ResponseModelOk()
