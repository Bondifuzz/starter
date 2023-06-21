from __future__ import annotations

from typing import TYPE_CHECKING

from starter.app.database.abstract import ILaunches
from starter.app.database.orm import ORMLaunch

from .base import DBBase
from .util import dbkey_to_id, maybe_unknown_error

if TYPE_CHECKING:
    from aioarangodb.collection import StandardCollection
    from aioarangodb.database import StandardDatabase

    from starter.app.settings import CollectionSettings


class DBLaunches(DBBase, ILaunches):

    _col_launches: StandardCollection

    def __init__(self, db: StandardDatabase, collections: CollectionSettings):
        self._col_launches = db[collections.launches]
        super().__init__(db, collections)

    @maybe_unknown_error
    async def save(self, launch: ORMLaunch) -> ORMLaunch:
        res = await self._col_launches.insert(launch.dict(exclude={"id"}))
        return ORMLaunch.parse_obj(dbkey_to_id({**res, **launch.dict()}))

    @maybe_unknown_error
    async def remove_expired(self):

        # fmt: off
        query, variables  ="""
            FOR launch in @@collection
                FILTER DATE_ISO8601(DATE_NOW()) > launch.exp_date
                REMOVE launch IN @@collection
        """, {
            "@collection": self._col_launches.name
        }
        # fmt: on

        await self._db.aql.execute(query, bind_vars=variables)
