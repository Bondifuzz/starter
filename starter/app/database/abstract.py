from __future__ import annotations

from abc import ABCMeta, abstractmethod
from typing import TYPE_CHECKING, Dict

from starter.app.database.orm import ORMLaunch
from starter.app.util.developer import testing_only

if TYPE_CHECKING:
    from starter.app.settings import AppSettings


class IUnsentMessages(metaclass=ABCMeta):

    """
    Used for saving/loading MQ unsent messages from database.
    """

    @abstractmethod
    async def save_unsent_messages(self, messages: Dict[str, list]):
        pass

    @abstractmethod
    async def load_unsent_messages(self) -> Dict[str, list]:
        pass


class ILaunches(metaclass=ABCMeta):

    """
    Used for saving pod launches to database
    """

    @abstractmethod
    async def save(self, launch: ORMLaunch):
        pass

    @abstractmethod
    async def remove_expired(self):
        pass


class IDatabase(metaclass=ABCMeta):

    """Used for managing database"""

    @staticmethod
    @abstractmethod
    async def create(cls, settings: AppSettings):
        pass

    @abstractmethod
    async def close(self) -> None:
        pass

    @property
    @abstractmethod
    def unsent_mq(self) -> IUnsentMessages:
        pass

    @property
    @abstractmethod
    def launches(self) -> ILaunches:
        pass

    @abstractmethod
    @testing_only
    async def truncate_all_collections(self) -> None:
        pass
