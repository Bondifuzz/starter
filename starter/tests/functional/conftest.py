from __future__ import annotations

import asyncio
import functools
import random
import string

import pytest

from starter.app.agent import AgentSpecTemplate
from starter.app.database import db_init
from starter.app.kubernetes.client import KubernetesClient
from starter.app.kubernetes.initializer import KubernetesInitializer
from starter.app.settings import AppSettings, load_app_settings

from .message_queue import mq_init


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.get_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
def settings():
    return load_app_settings()


@pytest.fixture(scope="session")
def template():
    return AgentSpecTemplate("agent.yaml")


@pytest.fixture(scope="session")
async def mq_app(settings):

    mq_app = await mq_init(settings)
    for channel in mq_app.consuming_channels:
        await channel.purge()

    await mq_app.start()
    yield mq_app
    await mq_app.shutdown()


@pytest.fixture(scope="session", autouse=True)
async def db(settings):
    db = await db_init(settings)
    await db.truncate_all_collections()
    yield db
    await db.close()


@pytest.fixture(scope="session")
async def k8s_client(settings):

    initializer = await KubernetesInitializer.create(settings)
    await initializer.do_init()

    client = await KubernetesClient.create(settings)
    await client.delete_all_pods()
    yield client
    await client.close()


@pytest.fixture()
async def fuzzer_data(settings):
    return FuzzerData(settings)


def random_string(n: int):
    return "".join(random.choices(string.ascii_letters, k=n))


class FuzzerData:
    def __init__(self, settings: AppSettings) -> None:
        self.id = random_string(8)
        self.rev = random_string(4)
        self.mode = "first-run"
        self.image = settings.kubernetes.testing_image_name
        self.container = "myfuzzer"
        self.cpu = "100m"
        self.ram = "50M"
        self.engine = "AFL"
        self.lang = "Cpp"
        self.cpu_int = 100
        self.ram_int = 50

    def to_dict(self):
        return {
            "fuzzer_id": self.id,
            "fuzzer_rev": self.rev,
            "agent_mode": self.mode,
            "fuzzer_engine": self.engine,
            "fuzzer_lang": self.lang,
            "fuzzer_image": self.image,
            "cpu_usage": self.cpu_int,
            "ram_usage": self.ram_int,
        }


def waits_for_events(func):
    @functools.wraps(func)
    async def wrapped(*args, **kwargs):
        try:
            res = await func(*args, **kwargs)
        except asyncio.TimeoutError:
            pytest.fail(
                f"[{func.__name__}] Waiting for event failed: reason - TimeoutError",
                False,
            )

        return res

    return wrapped
