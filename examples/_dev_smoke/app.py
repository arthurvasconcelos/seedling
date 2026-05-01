"""
Minimal FastAPI app exercising the seedling public API.

Run with:
    uv run uvicorn examples._dev_smoke.app:app --reload

Then:
    curl http://localhost:8000/seed
    curl http://localhost:8000/users
    curl http://localhost:8000/posts
"""

from __future__ import annotations

from fastapi import FastAPI
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from seedling import SeederRunner

from .models import Base, Post, User
from .seeders import PostSeeder, UserSeeder

DATABASE_URL = "sqlite+aiosqlite:///./smoke.db"

engine = create_async_engine(DATABASE_URL, echo=False)
session_factory = async_sessionmaker(engine, expire_on_commit=False)

app = FastAPI(title="seedling smoke test")


@app.on_event("startup")
async def startup() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


def _runner() -> SeederRunner:
    r = SeederRunner(session_factory, env="development")
    r.register(UserSeeder, PostSeeder)
    return r


@app.post("/seed")
async def seed() -> dict[str, str]:
    await _runner().run()
    return {"status": "seeded"}


@app.post("/fresh")
async def fresh() -> dict[str, str]:
    await _runner().fresh()
    return {"status": "freshly seeded"}


@app.get("/users")
async def list_users() -> list[dict[str, object]]:
    async with session_factory() as session:
        rows = (await session.execute(select(User))).scalars().all()
    return [{"id": u.id, "email": u.email, "name": u.name} for u in rows]


@app.get("/posts")
async def list_posts() -> list[dict[str, object]]:
    async with session_factory() as session:
        rows = (await session.execute(select(Post))).scalars().all()
    return [{"id": p.id, "title": p.title, "author_id": p.author_id} for p in rows]
