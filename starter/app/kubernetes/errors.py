import functools

from kubernetes_asyncio.client.exceptions import ApiException


class KubernetesInitError(Exception):
    pass


def wrap_k8s_errors(func):
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            result = await func(*args, **kwargs)
        except ApiException as e:
            raise KubernetesInitError(e) from e
        return result

    return wrapper
