import logging
import os
import sys


def setup_logging():
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    log_level_value = getattr(logging, log_level, logging.INFO)

    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)

    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        "%Y-%m-%d %H:%M:%S"
    )
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.setLevel(log_level_value)
    root_logger.addHandler(handler)

    noisy_libs = ["discord", "discord.client", "discord.gateway",
                  "pymongo", "motor", "asyncio"]

    for name in noisy_libs:
        logger = logging.getLogger(name)
        logger.setLevel(log_level_value)
        logger.handlers.clear()
        logger.addHandler(handler)
        logger.propagate = False

    logging.info(f"Logging initialized with level: {log_level}")
