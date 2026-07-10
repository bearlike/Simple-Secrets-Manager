#!/usr/bin/env python3

from loguru import logger

logger.add(
    "secrets_manager.log",
    enqueue=True,
    colorize=False,
    level="WARNING",
    rotation="8 MB",
    format="{time:DD-MM-YYYY HH:mm:ss} {level} {message}",
)


def init_app():
    import ssm_telemetry
    from ssm_server.api.api import app
    from ssm_server.api.core import settings
    from ssm_server.engines.versioning import get_application_version

    # Wire OTel event emission once, in the worker process. No-op unless the
    # OTLP endpoint is configured (and the `otel` extra is installed); the
    # endpoint is injected from settings, never read from the environment here.
    ssm_telemetry.configure(
        "ssm-server",
        get_application_version(),
        endpoint=settings.otel_exporter_otlp_endpoint,
    )

    app.run(
        debug=settings.debug,
        host=settings.bind_host,
        port=settings.port,
        use_reloader=settings.debug,
    )


if __name__ == "__main__":
    logger.info("Starting Secrets Manager")
    init_app()
