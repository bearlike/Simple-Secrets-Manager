#!/usr/bin/env python3

import os
from loguru import logger
from dotenv import load_dotenv

load_dotenv()

logger.add(
    "secrets_manager.log",
    enqueue=True,
    colorize=False,
    level="WARNING",
    rotation="8 MB",
    format="{time:DD-MM-YYYY HH:mm:ss} {level} {message}",
)


def strtobool(val: str) -> bool:
    """Convert a string representation of truth to True or False.

    True values are 'y', 'yes', 't', 'true', 'on', and '1';
    False values are 'n', 'no', 'f', 'false', 'off', and '0'.
    Raises ValueError if 'val' is anything else.
    """
    val = val.lower().strip()
    if val in ("y", "yes", "t", "true", "on", "1"):
        return True
    elif val in ("n", "no", "f", "false", "off", "0"):
        return False
    else:
        logger.warning(f"invalid truth value {val!r}")
        return False


def init_app():
    from Api.api import app

    debug_enabled = strtobool(os.getenv("DEBUG", "False"))
    app.run(
        debug=debug_enabled,
        host=os.environ.get("BIND_HOST", "0.0.0.0"),
        port=os.environ.get("PORT", 5000),
        use_reloader=debug_enabled,
    )


if __name__ == "__main__":
    logger.info("Starting Secrets Manager")
    init_app()
