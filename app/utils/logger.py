import logging
import sys
import time
from functools import wraps

# Setup standard formatting
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

def get_logger(name: str):
    return logging.getLogger(name)

# Latency timing decorator
def log_latency(logger_name: str = "performance"):
    logger = get_logger(logger_name)
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.perf_counter()
            try:
                result = func(*args, **kwargs)
                elapsed = time.perf_counter() - start_time
                logger.info(f"Method '{func.__name__}' executed in {elapsed:.4f}s")
                return result
            except Exception as e:
                elapsed = time.perf_counter() - start_time
                logger.error(f"Method '{func.__name__}' failed after {elapsed:.4f}s with error: {str(e)}")
                raise
        return wrapper
    return decorator
