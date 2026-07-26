"""Central loguru setup + stdlib-logging interception (uvicorn/sqlalchemy)."""
import logging
import os
import sys
from loguru import logger

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()


class InterceptHandler(logging.Handler):
    """Route stdlib logging (uvicorn, sqlalchemy) through loguru."""
    def emit(self, record):
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno
        frame, depth = logging.currentframe(), 2
        while frame and frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1
        logger.opt(depth=depth, exception=record.exc_info).log(level, record.getMessage())


def setup_logging():
    logger.remove()
    logger.add(sys.stderr, level=LOG_LEVEL, backtrace=True, diagnose=False,
               format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level:<8}</level> | "
                      "<cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>")
    logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access", "sqlalchemy.engine"):
        logging.getLogger(name).handlers = [InterceptHandler()]
        logging.getLogger(name).propagate = False
    # polars/fastexcel dtype-inference chatter -> errors only
    for name in ("polars", "fastexcel", "_fastexcel"):
        logging.getLogger(name).setLevel(logging.ERROR)
    logger.info("logging initialised at level {}", LOG_LEVEL)
