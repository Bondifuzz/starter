class DatabaseError(Exception):
    """Base exception for all database errors"""


class DBLaunchError(DatabaseError):
    pass


class DBLaunchNotFoundError(DBLaunchError):
    pass


class DBLaunchAlreadyExistsError(DBLaunchError):
    pass
