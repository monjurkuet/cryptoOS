import sys
from loguru import logger


def setup_logger(level: str = "INFO"):
    logger.remove()
    logger.add(
        sys.stdout,
        level=level,
        format="{time} | {level} | {message}",
        colorize=True,
    )
    return logger


def format_timestamp(timestamp: int) -> str:
    from datetime import datetime

    return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")


def retry_on_failure(max_retries: int = 3, delay: int = 1):
    import time

    def decorator(func):
        def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if attempt == max_retries - 1:
                        raise e
                    time.sleep(delay * (attempt + 1))
            return None

        return wrapper

    return decorator
