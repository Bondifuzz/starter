import functools
from typing import Type

from aioarangodb.errno import DOCUMENT_NOT_FOUND, UNIQUE_CONSTRAINT_VIOLATED
from aioarangodb.exceptions import (
    ArangoError,
    CursorEmptyError,
    DocumentDeleteError,
    DocumentInsertError,
    DocumentReplaceError,
)
from aiohttp.client_exceptions import ClientConnectionError

from starter.app.database.errors import DatabaseError


def dbkey_to_id(data: dict):
    data["id"] = data["_key"]
    del data["_key"]
    del data["_id"]
    del data["_rev"]
    return data


def id_to_dbkey(data: dict):
    data["_key"] = data["id"]
    del data["id"]
    return data


def maybe_unknown_error(func):
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            res = await func(*args, **kwargs)
        except (ArangoError, ClientConnectionError) as e:
            raise DatabaseError(e) from e

        return res

    return wrapper


def maybe_not_found(ExceptionRaised: Type[DatabaseError]):
    def wrapper(func):
        @functools.wraps(func)
        async def wrapped(*args, **kwargs):
            try:
                res = await func(*args, **kwargs)
            except CursorEmptyError as e:
                raise ExceptionRaised() from e
            except DocumentDeleteError as e:
                if e.error_code == DOCUMENT_NOT_FOUND:
                    raise ExceptionRaised() from e
                raise

            return res

        return wrapped

    return wrapper


def maybe_not_found_none(ExceptionRaised: Type[DatabaseError]):
    def wrapper(func):
        @functools.wraps(func)
        async def wrapped(*args, **kwargs):
            res = await func(*args, **kwargs)
            if not res:
                raise ExceptionRaised()

            return res

        return wrapped

    return wrapper


def maybe_already_exists(ExceptionRaised: Type[DatabaseError]):
    def wrapper(func):
        @functools.wraps(func)
        async def wrapped(*args, **kwargs):
            try:
                res = await func(*args, **kwargs)
            except (DocumentInsertError, DocumentReplaceError) as e:
                if e.error_code == UNIQUE_CONSTRAINT_VIOLATED:
                    raise ExceptionRaised() from e
                raise
            return res

        return wrapped

    return wrapper
