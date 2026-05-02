"""
FastAPI + Alembic example app.

Run with:
    cd examples/fastapi_alembic
    alembic upgrade head
    uvicorn app.main:app --reload

Then seed the database:
    seed run --env development

Or run via the API:
    curl -X POST http://localhost:8000/seed
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from sqlalchemy import select

from examples.fastapi_alembic.app.database import async_session
from examples.fastapi_alembic.app.models import Post, User


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    yield


app = FastAPI(title="seedling — FastAPI + Alembic example", lifespan=lifespan)


@app.post("/seed")
async def seed_development() -> dict[str, str]:
    from examples.fastapi_alembic.app.seeders import create_runner
    await create_runner("development").run()
    return {"status": "seeded"}


@app.post("/fresh")
async def fresh_development() -> dict[str, str]:
    from examples.fastapi_alembic.app.seeders import create_runner
    await create_runner("development").fresh()
    return {"status": "freshly seeded"}


@app.get("/users")
async def list_users() -> list[dict[str, object]]:
    async with async_session() as session:
        rows = (await session.execute(select(User))).scalars().all()
    return [{"id": u.id, "email": u.email, "name": u.name} for u in rows]


@app.get("/posts")
async def list_posts() -> list[dict[str, object]]:
    async with async_session() as session:
        rows = (await session.execute(select(Post))).scalars().all()
    return [{"id": p.id, "title": p.title, "author_id": p.author_id} for p in rows]
