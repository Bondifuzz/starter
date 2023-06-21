from contextlib import suppress
from typing import Any, Dict, Optional

from prometheus_client import Enum
from pydantic import AnyHttpUrl, AnyUrl, BaseModel
from pydantic import BaseSettings as _BaseSettings
from pydantic import Field, root_validator, validator

from starter.app.util.datetime import duration_in_seconds
from starter.app.util.resources import CpuResources, RamResources

# fmt: off
with suppress(ModuleNotFoundError):
    import dotenv; dotenv.load_dotenv()
# fmt: on


class BaseSettings(_BaseSettings):
    @root_validator
    def check_empty_strings(cls, data: Dict[str, Any]):
        for name, value in data.items():
            if isinstance(value, str):
                if len(value) == 0:
                    var = f"{cls.__name__}.{name}"
                    raise ValueError(f"Variable '{var}': empty string not allowed")

        return data


class CollectionSettings(BaseSettings):
    unsent_messages = "UnsentMessages"
    operations = "Operations"
    launches = "Launches"
    pools = "Pools"


class DatabaseSettings(BaseSettings):

    engine: str = Field(regex=r"^arangodb$")
    url: AnyHttpUrl
    username: str
    password: str
    name: str

    class Config:
        env_prefix = "DB_"


class EnvironmentSettings(BaseSettings):

    name: str = Field(env="ENVIRONMENT", regex=r"^(dev|prod|test)$")
    shutdown_timeout: int = Field(env="SHUTDOWN_TIMEOUT")
    service_name: Optional[str] = Field(env="SERVICE_NAME")
    service_version: Optional[str] = Field(env="SERVICE_VERSION")
    commit_id: Optional[str] = Field(env="COMMIT_ID")
    build_date: Optional[str] = Field(env="BUILD_DATE")
    commit_date: Optional[str] = Field(env="COMMIT_DATE")
    git_branch: Optional[str] = Field(env="GIT_BRANCH")

    @validator("shutdown_timeout", pre=True)
    def validate_duration(value: Optional[str]):
        return duration_in_seconds(value or "")

    @root_validator(skip_on_failure=True)
    def check_values_for_production(cls, data: Dict[str, Any]):

        if data["name"] != "prod":
            return data

        vars = []
        for name, value in data.items():
            if value is None:
                vars.append(name.upper())

        if vars:
            raise ValueError(f"Variables must be set in production mode: {vars}")

        return data


class PodOutputSaveMode(str, Enum):

    none = "None"
    """ Do not store any pod output """

    err = "Error"
    """ Store only failed pod output  """

    all = "All"
    """ Store output of each pod """


class FuzzerPodSettings(BaseSettings):

    min_work_time: int
    """ Minimal pod work time (displacement algorithm) """

    namespace: str
    """ Kuberenetes namespace where pods will be run """

    test_run_image: str
    """ Docker image name for test runs """

    agent_cpu: int
    """ Agent container CPU usage (mcpu) """

    agent_ram: int
    """ Agent container RAM usage (MiB) """

    output_save_mode: PodOutputSaveMode
    """ Defines what pod output will be saved to database """

    launch_info_retention_period: int
    """ How long to store the saved pod output in a database """

    launch_info_cleanup_interval: int
    """ How often to do fuzzer saved launch info cleanup """

    class Config:
        env_prefix = "POD_"

    @validator(
        "min_work_time",
        "launch_info_retention_period",
        "launch_info_cleanup_interval",
        pre=True,
    )
    def validate_duration(value: Optional[str]):
        return duration_in_seconds(value or "")

    @validator("agent_cpu", pre=True)
    def validate_cpu(value: Optional[str]):
        return CpuResources.from_string(value or "")

    @validator("agent_ram", pre=True)
    def validate_ram(value: Optional[str]):
        return RamResources.from_string(value or "")


class ContainerRegistrySettings(BaseSettings):

    url: str
    """ Container registry endpoint without 'https://' scheme """

    class Config:
        env_prefix = "CONTAINER_REGISTRY_"


class MessageQueues(BaseSettings):

    scheduler: str

    class Config:
        env_prefix = "MQ_QUEUE_"


class MessageQueueSettings(BaseSettings):

    username: str
    password: str
    region: str
    url: Optional[AnyUrl]
    queues: MessageQueues
    broker: str = Field(regex=r"^sqs$")

    class Config:
        env_prefix = "MQ_"


class APIEndpoints(BaseSettings):
    pool_manager: AnyHttpUrl

    class Config:
        env_prefix = "API_URL_"


class AppSettings(BaseModel):
    database: DatabaseSettings
    collections: CollectionSettings
    registry: ContainerRegistrySettings
    fuzzer_pod: FuzzerPodSettings
    environment: EnvironmentSettings
    message_queue: MessageQueueSettings
    api_endpoints: APIEndpoints


_app_settings = None


def get_app_settings() -> AppSettings:

    global _app_settings

    if _app_settings is None:
        _app_settings = AppSettings(
            database=DatabaseSettings(),
            collections=CollectionSettings(),
            registry=ContainerRegistrySettings(),
            message_queue=MessageQueueSettings(queues=MessageQueues()),
            fuzzer_pod=FuzzerPodSettings(),
            environment=EnvironmentSettings(),
            api_endpoints=APIEndpoints(),
        )

    return _app_settings
