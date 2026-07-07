from fastapi import FastAPI
from fastapi.responses import JSONResponse

from app.exceptions.base import AppException
from app.logging.logger import logger


def register_exception_handlers(app: FastAPI) -> None:

    @app.exception_handler(AppException)
    async def app_exception_handler(request, exc: AppException):
        logger.warning(f"AppException handled: {exc.message} (status_code={exc.status_code})")
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.message})
