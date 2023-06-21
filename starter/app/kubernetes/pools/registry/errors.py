class ResourcePoolError(Exception):
    pass


class PoolNodeAlreadyExistsError(ResourcePoolError):
    pass


class PoolNodeNotFoundError(ResourcePoolError):
    pass


class PoolNoResourcesLeftError(ResourcePoolError):
    pass


class PoolOverflowError(ResourcePoolError):
    pass


class PoolUnderflowError(ResourcePoolError):
    pass


class PoolCapacityExceededError(ResourcePoolError):
    pass


class PoolLockedError(ResourcePoolError):
    pass


class PoolRegistryError(Exception):
    pass


class PoolNotFoundError(PoolRegistryError):
    pass


class PoolAlreadyExistsError(PoolRegistryError):
    pass
