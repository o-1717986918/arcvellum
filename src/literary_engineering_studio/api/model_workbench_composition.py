"""HTTP assembly for model configuration and isolated creative workbenches."""
from ..application.container import ApplicationContainer
from .routers.pi_worker import build_pi_worker_router
from .routers.tone_experiment import build_tone_experiment_router
from .routers.prompts import build_prompts_router
from .routers.character_chat import build_character_chat_router
from .routers.stylometry import build_stylometry_router
from .routers.stylometry_jobs import build_stylometry_jobs_router


def register_model_workbench_routers(app, config, container: ApplicationContainer) -> None:
    app.include_router(build_pi_worker_router(config))
    app.include_router(build_tone_experiment_router(config))
    for service, builder in ((container.services.prompts, build_prompts_router),
        (container.services.character_chat, build_character_chat_router),
        (container.services.stylometry, build_stylometry_router),
        (container.services.stylometry_jobs, build_stylometry_jobs_router)):
        if service is not None:
            app.include_router(builder(service))
