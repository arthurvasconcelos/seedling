from __future__ import annotations

from seedling.factory import Factory, post_generation
from tests.conftest import Article, Author, Item


# ── basic: fires after create, skipped in build ─────────────────────────────


async def test_post_generation_fires_after_create(session):
    calls: list[tuple[object, object]] = []

    class ItemFactory(Factory[Item]):
        model = Item
        name = "item"
        value = 0

        @post_generation
        async def record_call(instance, sess):
            calls.append((instance, sess))

    await ItemFactory.create(session)
    assert len(calls) == 1
    assert calls[0][1] is session


def test_post_generation_skipped_in_build():
    calls: list[object] = []

    class ItemFactory(Factory[Item]):
        model = Item
        name = "item"
        value = 0

        @post_generation
        async def record_call(instance, sess):
            calls.append(instance)

    ItemFactory.build()
    assert calls == []


# ── instance is persisted when hook fires ─────────────────────────────────────


async def test_post_generation_receives_flushed_instance(session):
    seen_id: list[int | None] = []

    class ItemFactory(Factory[Item]):
        model = Item
        name = "item"
        value = 0

        @post_generation
        async def capture_id(instance, sess):
            seen_id.append(instance.id)

    item = await ItemFactory.create(session)
    assert seen_id[0] is not None
    assert seen_id[0] == item.id


# ── hook can create related rows ──────────────────────────────────────────────


async def test_post_generation_can_create_related_rows(session):
    created_articles: list[Article] = []

    class AuthorFactory(Factory[Author]):
        model = Author
        email = "a@example.com"
        first_name = "A"

        @post_generation
        async def add_article(instance, sess):
            article = Article(title="auto-article", author_id=instance.id)
            sess.add(article)
            await sess.flush()
            await sess.refresh(article)
            created_articles.append(article)

    author = await AuthorFactory.create(session)
    assert len(created_articles) == 1
    assert created_articles[0].author_id == author.id


# ── multiple hooks fire in definition order ────────────────────────────────────


async def test_post_generation_multiple_hooks_fire_in_order(session):
    order: list[str] = []

    class ItemFactory(Factory[Item]):
        model = Item
        name = "item"
        value = 0

        @post_generation
        async def first(instance, sess):
            order.append("first")

        @post_generation
        async def second(instance, sess):
            order.append("second")

    await ItemFactory.create(session)
    assert order == ["first", "second"]


# ── child factory inherits parent hooks ───────────────────────────────────────


async def test_post_generation_inherited_from_parent(session):
    calls: list[str] = []

    class BaseFactory(Factory[Item]):
        model = Item
        name = "item"
        value = 0

        @post_generation
        async def parent_hook(instance, sess):
            calls.append("parent")

    class ChildFactory(BaseFactory):
        pass

    await ChildFactory.create(session)
    assert calls == ["parent"]


# ── child can override parent hook by same name ───────────────────────────────


async def test_post_generation_child_overrides_parent_hook(session):
    calls: list[str] = []

    class BaseFactory(Factory[Item]):
        model = Item
        name = "item"
        value = 0

        @post_generation
        async def setup(instance, sess):
            calls.append("parent")

    class ChildFactory(BaseFactory):
        @post_generation
        async def setup(instance, sess):
            calls.append("child")

    await ChildFactory.create(session)
    assert calls == ["child"]


# ── sync hook accepted ────────────────────────────────────────────────────────


async def test_post_generation_sync_hook_accepted(session):
    calls: list[object] = []

    class ItemFactory(Factory[Item]):
        model = Item
        name = "item"
        value = 0

        @post_generation
        def sync_hook(instance, sess):
            calls.append(instance)

    item = await ItemFactory.create(session)
    assert len(calls) == 1
    assert calls[0] is item


# ── fires once per item in create_batch ───────────────────────────────────────


async def test_post_generation_fires_per_item_in_batch(session):
    calls: list[int] = []

    class ItemFactory(Factory[Item]):
        model = Item
        name = "item"
        value = 0

        @post_generation
        async def count_calls(instance, sess):
            calls.append(instance.id)

    items = await ItemFactory.create_batch(session, 3)
    assert len(calls) == 3
    assert set(calls) == {i.id for i in items}
