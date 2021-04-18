import time


def time_logger(logger):
    def timer(func):
        def wrapper(*args, **kwargs):
            start = time.time()
            result = func(*args, **kwargs)
            end = time.time()
            elapse = end - start
            logger.info(
                "%s takes %s seconds",
                func.__name__, elapse
            )
            return result
        return wrapper
    return timer
