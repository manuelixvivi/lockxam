import time
import uuid

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

from app.logging.logger import ip_var, logger, request_id_var


class RequestContextMiddleware(BaseHTTPMiddleware):

    async def dispatch(self, request: Request, call_next):
        # 1. Generate or retrieve request ID
        req_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        ip = request.client.host if request.client else "127.0.0.1"

        # 2. Set context variables for context-aware logger
        token_id = request_id_var.set(req_id)
        token_ip = ip_var.set(ip)

        # 3. Store in request state for downstream usage
        request.state.request_id = req_id
        request.state.ip = ip
        request.state.user_agent = request.headers.get("user-agent", "unknown")

        start_time = time.time()
        logger.info(f"Incoming request: {request.method} {request.url.path}")

        try:
            response = await call_next(request)

            # 4. Measure latency
            process_time = time.time() - start_time
            logger.info(
                f"Finished request: {request.method} {request.url.path} "
                f"Status: {response.status_code} Time: {process_time:.4f}s"
            )

            # 5. Attach tracking and security headers to response
            response.headers["X-Request-ID"] = req_id
            response.headers["X-Process-Time"] = f"{process_time:.4f}s"
            response.headers["X-Content-Type-Options"] = "nosniff"
            return response

        except Exception as e:
            process_time = time.time() - start_time
            logger.error(
                f"Request failed: {request.method} {request.url.path} "
                f"Error: {str(e)} Time: {process_time:.4f}s"
            )
            raise
        finally:
            # 6. Clean up context variables to prevent memory leaks
            request_id_var.reset(token_id)
            ip_var.reset(token_ip)
