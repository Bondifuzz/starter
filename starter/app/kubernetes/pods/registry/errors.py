class PodRegistryError(Exception):
    pass


class PodNotFoundError(PodRegistryError):
    pass


class PodAlreadyExistsError(PodRegistryError):
    pass
