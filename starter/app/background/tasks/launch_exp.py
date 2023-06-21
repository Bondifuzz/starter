from starter.app.database.abstract import IDatabase
from starter.app.settings import AppSettings

from ..bg_task import BackgroundTask


class FuzzerSavedLaunchCleaner(BackgroundTask):

    _db: IDatabase

    def __init__(self, settings: AppSettings, db: IDatabase) -> None:
        name = self.__class__.__name__
        wait_interval = settings.fuzzer_pod.launch_info_cleanup_interval
        super().__init__(name, wait_interval)
        self._db = db

    async def _task_coro(self):
        await self._db.launches.remove_expired()
        self._logger.debug("Fuzzer saved launch cleanup is done")
