"""
Litestar example app.

Run with:
    uvicorn examples.litestar.app.main:app --reload

Then seed the database:
    seed run --env development

Or via the API:
    curl -X POST http://localhost:8000/seed
"""

from __future__ import annotations

from litestar import Litestar, get, post
from sqlalchemy import select

from examples.litestar.app.database import async_session
from examples.litestar.app.models import Base, Post, User


async def on_startup() -> None:
    from examples.litestar.app.database import engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


@post("/seed")
async def seed_development() -> dict[str, str]:
    from examples.litestar.app.seeders import create_runner
    await create_runner("development").run()
    return {"status": "seeded"}


@post("/fresh")
async def fresh_development() -> dict[str, str]:
    from examples.litestar.app.seeders import create_runner
    await create_runner("development").fresh()
    return {"status": "freshly seeded"}


@get("/users")
async def list_users() -> list[dict[str, object]]:
    async with async_session() as session:
        rows = (await session.execute(select(User))).scalars().all()
    return [{"id": u.id, "email": u.email, "name": u.name} for u in rows]


@get("/posts")
async def list_posts() -> list[dict[str, object]]:
    async with async_session() as session:
        rows = (await session.execute(select(Post))).scalars().all()
    return [{"id": p.id, "title": p.title, "author_id": p.author_id} for p in rows]


app = Litestar(
    route_handlers=[seed_development, fresh_development, list_users, list_posts],
    on_startup=[on_startup],
)
