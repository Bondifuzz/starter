from starter.app.settings import AppSettings


def sandbox_image_name(image_id: str, settings: AppSettings) -> str:
    return f"{settings.registry.url}/sandbox/{image_id.lower()}"


def agent_image_name(fuzzer_engine: str, settings: AppSettings) -> str:
    return f"{settings.registry.url}/agents/{fuzzer_engine.lower()}"  # TODO: make lower() in request model, not there


def test_run_image_name(settings: AppSettings) -> str:
    image = settings.fuzzer_pod.test_run_image
    return f"{settings.registry.url}/{image.lower()}"
