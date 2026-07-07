import contextvars
import logging
import sys

# Context variables to hold request-scoped information
request_id_var = contextvars.ContextVar("request_id", default="N/A")
ip_var = contextvars.ContextVar("ip", default="N/A")


class ContextFilter(logging.Filter):

    def filter(self, record):
        record.request_id = request_id_var.get()
        record.ip = ip_var.get()
        return True


# Configure basic logging with a clean format
logger = logging.getLogger("equigrade")
logger.setLevel(logging.INFO)

if not logger.handlers:
    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] [%(ip)s] [ReqID: %(request_id)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.addFilter(ContextFilter())
