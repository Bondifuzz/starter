from __future__ import annotations

import logging
import sys
from contextlib import contextmanager
from typing import TYPE_CHECKING, Iterator

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.routing import APIRoute
from mqtransport.errors import MQTransportError
from starlette.status import HTTP_500_INTERNAL_SERVER_ERROR

from starter.app.api.error_codes import E_INTERNAL_ERROR
from starter.app.api.error_model import error_details
from starter.app.background.manager import BackgroundTaskManager
from starter.app.background.tasks.launch_exp import FuzzerSavedLaunchCleaner
from starter.app.database.errors import DatabaseError
from starter.app.external_api.errors import ExternalAPIError
from starter.app.external_api.external_api import ExternalAPI
from starter.app.kubernetes.client import KubernetesClient
from starter.app.kubernetes.initializer import KubernetesInitializer
from starter.app.kubernetes.pods.events.event_handler import PodEventHandler
from starter.app.kubernetes.pods.events.event_listener import PodEventListener
from starter.app.kubernetes.pods.registry import FuzzerPodRegistry, pod_registry_init
from starter.app.kubernetes.pools.events.event_handler import PoolEventHandler
from starter.app.kubernetes.pools.events.event_listener import PoolEventListener
from starter.app.kubernetes.pools.registry import PoolRegistry, pool_registry_init
from starter.app.message_queue import MQAppState, mq_init
from starter.app.spec.agent import AgentSpecTemplate

from . import api
from .database.instance import db_init
from .settings import AppSettings, get_app_settings

# from .utils.json import JSONResponse, json_dumps
from .util.speedup.json import JSONResponse, dumps

if TYPE_CHECKING:
    from mqtransport import MQApp

    from .database.abstract import IDatabase


def configure_exception_handlers(app):

    # Common error response format
    def error_response():

        content = {
            "status": "FAILED",
            **error_details(E_INTERNAL_ERROR),
        }

        return JSONResponse(content, HTTP_500_INTERNAL_SERVER_ERROR)

    @app.exception_handler(DatabaseError)
    async def db_exception_handler(request: Request, e: DatabaseError):
        operation = request.state.operation
        route = f"{request.method} {request.url.path}"
        msg = "Unexpected DB error: %s. Operation: '%s'. Route: '%s'"
        logging.getLogger("db").error(msg, e, operation, route)
        return error_response()

    @app.exception_handler(MQTransportError)
    async def mq_exception_handler(request: Request, e: MQTransportError):
        operation = request.state.operation
        route = f"{request.method} {request.url.path}"
        msg = "Unexpected MQ error: %s. Operation: '%s'. Route: '%s'"
        logging.getLogger("mq").error(msg, e, operation, route)
        return error_response()

    @app.exception_handler(ExternalAPIError)
    async def external_api_exception_handler(request: Request, e: ExternalAPIError):
        operation = request.state.operation
        route = f"{request.method} {request.url.path}"
        msg = "Unexpected external API error: %s. Operation: '%s'. Route: '%s'"
        logging.getLogger("api.external").error(msg, e, operation, route)
        return error_response()


class AppState:
    k8s_client: KubernetesClient
    pod_listener: PodEventListener
    pool_listener: PoolEventListener
    agent_template: AgentSpecTemplate
    pod_registry: FuzzerPodRegistry
    pool_registry: PoolRegistry
    bg_task_mgr: BackgroundTaskManager
    external_api: ExternalAPI
    db: IDatabase
    mq_app: MQApp


def configure_startup_events(app: FastAPI, settings: AppSettings):

    logger = logging.getLogger("main")

    @contextmanager
    def startup_helper(msg: str) -> Iterator[AppState]:
        logger.info(f"{msg}...")
        yield app.state
        logger.info(f"{msg}... OK")

    @app.on_event("startup")
    async def verify_k8s_permissions():
        with startup_helper("Verifying kubernetes"):
            initializer = await KubernetesInitializer.create(settings)
            await initializer.do_init()

    @app.on_event("startup")
    async def init_external_api():
        with startup_helper("Creating external API sessions") as state:
            state.external_api = await ExternalAPI.create(settings)

    @app.on_event("startup")
    async def init_k8s_client():
        with startup_helper("Creating kubernetes client") as state:
            state.k8s_client = await KubernetesClient.create(settings)

    @app.on_event("startup")
    async def init_database():
        with startup_helper("Configuring database") as state:
            state.db = await db_init(settings)

    @app.on_event("startup")
    async def init_message_queue():
        with startup_helper("Configuring message queue") as app_state:
            mq_app = await mq_init(settings)
            mq_state: MQAppState = mq_app.state
            mq_state.settings = settings
            mq_state.db = app_state.db
            app_state.mq_app = mq_app
            mq_state.fastapi = app

    @app.on_event("startup")
    async def init_pod_registry():
        with startup_helper("Creating pod registry") as state:
            state.pod_registry = await pod_registry_init(
                state.k8s_client,  # fmt: skip
            )

    @app.on_event("startup")
    async def init_pool_registry():
        with startup_helper("Creating pool registry") as state:
            state.pool_registry = await pool_registry_init(
                state.pod_registry, state.external_api  # fmt: skip
            )

    @app.on_event("startup")
    async def init_pool_event_listener():
        with startup_helper("Creating pool event listener") as state:

            pool_event_handler = PoolEventHandler(
                state.pool_registry,
                state.k8s_client,
            )

            state.pool_listener = PoolEventListener(
                pool_event_handler,
                state.external_api,
            )

            await state.pool_listener.start()

    @app.on_event("startup")
    async def init_pod_event_listener():
        with startup_helper("Creating pod event listener") as state:

            def create_pod_event_handler():
                return PodEventHandler(
                    state.mq_app,
                    state.db,
                    state.pool_registry,
                    state.pod_registry,
                    state.k8s_client,
                    settings,
                )

            state.pod_listener = await PodEventListener.create(
                create_pod_event_handler(),
                settings,
            )

            await state.pod_listener.start()

    @app.on_event("startup")
    async def init_background_task_manager():
        with startup_helper("Starting background tasks") as state:
            bg_task_mgr = BackgroundTaskManager()
            bg_task_mgr.add_task(FuzzerSavedLaunchCleaner(settings, state.db))
            state.bg_task_mgr = bg_task_mgr
            bg_task_mgr.start_tasks()

    @app.on_event("startup")
    async def import_unsent_messages_then_run():
        with startup_helper("Loading MQ unsent messages") as state:
            messages = await state.db.unsent_mq.load_unsent_messages()
            state.mq_app.import_unsent_messages(messages)
            await state.mq_app.start()


def configure_shutdown_events(app: FastAPI, settings: AppSettings):

    logger = logging.getLogger("main")

    @contextmanager
    def shutdown_helper(msg: str) -> Iterator[AppState]:
        logger.info(f"{msg}...")
        yield app.state
        logger.info(f"{msg}... OK")

    @app.on_event("shutdown")
    async def exit_background_task_manager():
        with shutdown_helper("Stopping background tasks") as state:
            await state.bg_task_mgr.stop_tasks()

    @app.on_event("shutdown")
    async def exit_pod_event_listener():
        with shutdown_helper("Closing pod event listener") as state:
            await state.pod_listener.close()

    @app.on_event("shutdown")
    async def exit_kubernetes_client():
        with shutdown_helper("Closing kubernetes client session") as state:
            await state.k8s_client.close()

    @app.on_event("shutdown")
    async def exit_pool_event_listener():
        with shutdown_helper("Closing pool event listener") as state:
            await state.pool_listener.close()

    @app.on_event("shutdown")
    async def exit_external_api():
        with shutdown_helper("Closing external API sessions") as state:
            await state.external_api.close()

    @app.on_event("shutdown")
    async def exit_message_queue():
        with shutdown_helper("Closing message queue") as state:
            timeout = settings.environment.shutdown_timeout
            await state.mq_app.shutdown(timeout)

    @app.on_event("shutdown")
    async def export_unsent_messages():
        with shutdown_helper("Saving MQ unsent messages") as state:
            messages = state.mq_app.export_unsent_messages()
            await state.db.unsent_mq.save_unsent_messages(messages)

    @app.on_event("shutdown")
    async def exit_database():
        with shutdown_helper("Closing database") as state:
            await state.db.close()


def configure_routes(app: FastAPI):

    logger = logging.getLogger("main")
    logger.info("Configuring routes...")

    pfx = "/api/v1"
    app.include_router(api.fuzzers.router, prefix=pfx)
    app.include_router(api.metrics.router)

    with open("index.html") as f:
        index_html = f.read()

    @app.get("/")
    async def index():
        return HTMLResponse(index_html)

    # Simplify openapi.json
    for route in app.routes:
        if isinstance(route, APIRoute):
            route.operation_id = route.name

    logger.info("Configuring routes... OK")


def generate_api_spec():

    app = FastAPI()
    configure_routes(app)

    print("Generating openapi.json...")

    with open("openapi.json", "w") as f:
        f.write(dumps(app.openapi()))

    print("Generating openapi.json... OK")
    sys.exit(0)


def create_app():

    app = FastAPI(default_response_class=JSONResponse)

    settings = get_app_settings()
    logging.info("%-16s %s", "ENVIRONMENT", settings.environment.name)
    logging.info("%-16s %s", "SERVICE_NAME", settings.environment.service_name)
    logging.info("%-16s %s", "SERVICE_VERSION", settings.environment.service_version)
    logging.info("%-16s %s", "COMMIT_ID", settings.environment.commit_id)
    logging.info("%-16s %s", "BUILD_DATE", settings.environment.build_date)
    logging.info("%-16s %s", "COMMIT_DATE", settings.environment.commit_date)
    logging.info("%-16s %s", "GIT_BRANCH", settings.environment.git_branch)

    configure_routes(app)
    configure_startup_events(app, settings)
    configure_shutdown_events(app, settings)
    configure_exception_handlers(app)
    return app
