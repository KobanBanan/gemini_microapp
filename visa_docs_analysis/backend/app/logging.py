from __future__ import annotations

import logging
from typing import Any

import structlog


def configure_logging(env: str = "dev") -> None:
    """Configure JSON logging via structlog.

    Args:
        env: Environment name; in dev add pretty console renderer.
    """

    timestamper = structlog.processors.TimeStamper(fmt="iso")

    processors: list[Any] = [
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        timestamper,
    ]

    if env == "dev":
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.processors.JSONRenderer())

    structlog.configure(
        processors=processors,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    # Bridge stdlib logging to structlog
    logging.basicConfig(level=logging.INFO, format="%(message)s")
