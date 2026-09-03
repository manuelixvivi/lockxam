from fastapi import APIRouter
from sqlalchemy import text

from app.core.database import engine

router = APIRouter(prefix="/health", tags=["Health"])


@router.get("")
@router.get("/")
async def health():
    return {"status": "ok"}


@router.get("/db")
async def db_health():

    with engine.connect() as conn:

        conn.execute(text("SELECT 1"))

    return {"database": "connected"}


@router.get("/tables")
async def tables():

    with engine.connect() as conn:

        result = conn.execute(text("""
                SELECT tablename
                FROM pg_tables
                WHERE schemaname='public'
                ORDER BY tablename
            """))

        tables = [row[0] for row in result]

    return {"tables": tables}
