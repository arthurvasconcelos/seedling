from __future__ import annotations

import pytest

from seedling.factory import (
    AutoFactory,
    Factory,
    RelatedFactory,
    RelatedFactoryList,
    Sequence,
    SubFactory,
    post_generation,
)
from tests.conftest import Article, Author, Item


@pytest.fixture(autouse=True)
def isolated_registry():
    from seedling.factory import _registry

    snapshot = dict(_registry)
    yield
    _registry.clear()
    _registry.update(snapshot)


# ── _can_use_fast_batch() detection ─────────────────────────────────────────


def test_plain_factory_can_use_fast_batch():
    class PlainFactory(Factory[Item]):
        model = Item
        name = Sequence(lambda n: f"item-{n}")
        value = 0

    assert PlainFactory._can_use_fast_batch() is True


def test_autofactory_without_fk_can_use_fast_batch():
    class ItemAutoFactory(AutoFactory[Item]):
        model = Item

    assert ItemAutoFactory._can_use_fast_batch() is True


def test_factory_with_post_generation_cannot_use_fast_batch():
    class HookedFactory(Factory[Item]):
        model = Item
        name = "item"
        value = 0

        @post_generation
        async def setup(instance, sess):
            pass

    assert HookedFactory._can_use_fast_batch() is False


def test_factory_with_related_factory_cannot_use_fast_batch():
    class ItemFactory(Factory[Item]):
        model = Item
        name = "item"
        value = 0

    class AuthorWithRelated(Factory[Author]):
        model = Author
        email = Sequence(lambda n: f"e{n}@example.com")
        first_name = "Author"
        related = RelatedFactory(ItemFactory)

    assert AuthorWithRelated._can_use_fast_batch() is False


def test_factory_with_related_factory_list_cannot_use_fast_batch():
    class ItemFactory(Factory[Item]):
        model = Item
        name = "item"
        value = 0

    class AuthorWithList(Factory[Author]):
        model = Author
        email = Sequence(lambda n: f"e{n}@example.com")
        first_name = "Author"
        related = RelatedFactoryList(ItemFactory, size=2)

    assert AuthorWithList._can_use_fast_batch() is False


def test_factory_with_subfactory_cannot_use_fast_batch():
    class AuthorFactory(Factory[Author]):
        model = Author
        email = Sequence(lambda n: f"e{n}@example.com")
        first_name = "Author"

    class ArticleWithSub(Factory[Article]):
        model = Article
        title = Sequence(lambda n: f"title-{n}")
        author = SubFactory(AuthorFactory)

    assert ArticleWithSub._can_use_fast_batch() is False


def test_autofactory_with_fk_cannot_use_fast_batch():
    """AutoFactory auto-generates _FKSubFactory for non-nullable FK columns."""

    class AuthorAutoFactory(AutoFactory[Author]):
        model = Author

    class ArticleAutoFactory(AutoFactory[Article]):
        model = Article

    assert ArticleAutoFactory._can_use_fast_batch() is False


def test_can_use_fast_batch_cached():
    class CachingFactory(Factory[Item]):
        model = Item
        name = Sequence(lambda n: f"item-{n}")
        value = 0

    CachingFactory._can_use_fast_batch()
    assert "_fast_batch_cache" in CachingFactory.__dict__


def test_each_subclass_caches_independently():
    class PlainFactory(Factory[Item]):
        model = Item
        name = Sequence(lambda n: f"item-{n}")
        value = 0

    class HookedFactory(Factory[Item]):
        model = Item
        name = "item"
        value = 0

        @post_generation
        async def setup(instance, sess):
            pass

    assert PlainFactory._can_use_fast_batch() is True
    assert HookedFactory._can_use_fast_batch() is False
    assert PlainFactory.__dict__["_fast_batch_cache"] is True
    assert HookedFactory.__dict__["_fast_batch_cache"] is False


# ── create_batch() fast-lane behaviour ───────────────────────────────────────


async def test_fast_batch_correct_count(session):
    class ItemFactory(Factory[Item]):
        model = Item
        name = Sequence(lambda n: f"item-{n}")
        value = 0

    items = await ItemFactory.create_batch(session, 5)
    assert len(items) == 5


async def test_fast_batch_count_zero_returns_empty(session):
    class ItemFactory(Factory[Item]):
        model = Item
        name = Sequence(lambda n: f"item-{n}")
        value = 0

    result = await ItemFactory.create_batch(session, 0)
    assert result == []


async def test_fast_batch_count_one(session):
    class ItemFactory(Factory[Item]):
        model = Item
        name = Sequence(lambda n: f"item-{n}")
        value = 0

    items = await ItemFactory.create_batch(session, 1)
    assert len(items) == 1
    assert items[0].id is not None


async def test_fast_batch_instances_have_distinct_pks(session):
    class ItemFactory(Factory[Item]):
        model = Item
        name = Sequence(lambda n: f"item-{n}")
        value = 0

    items = await ItemFactory.create_batch(session, 10)
    ids = [i.id for i in items]
    assert len(ids) == len(set(ids))


async def test_fast_batch_instances_are_orm_objects(session):
    class ItemFactory(Factory[Item]):
        model = Item
        name = Sequence(lambda n: f"item-{n}")
        value = 0

    items = await ItemFactory.create_batch(session, 3)
    assert all(isinstance(i, Item) for i in items)


async def test_fast_batch_field_values_correct(session):
    class ItemFactory(Factory[Item]):
        model = Item
        name = "fixed-name"
        value = 99

    items = await ItemFactory.create_batch(session, 3)
    for item in items:
        assert item.name == "fixed-name"
        assert item.value == 99


async def test_fast_batch_overrides_applied(session):
    class ItemFactory(Factory[Item]):
        model = Item
        name = Sequence(lambda n: f"item-{n}")
        value = 0

    items = await ItemFactory.create_batch(session, 3, name="override", value=7)
    for item in items:
        assert item.name == "override"
        assert item.value == 7


async def test_fast_batch_sequence_advances_per_row(session):
    class ItemFactory(Factory[Item]):
        model = Item
        name = Sequence(lambda n: f"item-{n}")
        value = Sequence(lambda n: n)

    ItemFactory.reset_sequence(0)
    items = await ItemFactory.create_batch(session, 3)
    names = [i.name for i in items]
    assert len(set(names)) == 3


# ── slow-path fallback with hooks ────────────────────────────────────────────


async def test_slow_path_post_generation_fires_per_row(session):
    calls: list[int | None] = []

    class ItemFactory(Factory[Item]):
        model = Item
        name = Sequence(lambda n: f"item-{n}")
        value = 0

        @post_generation
        async def record(instance, sess):
            calls.append(instance.id)

    items = await ItemFactory.create_batch(session, 3)
    assert len(items) == 3
    assert len(calls) == 3
    assert all(pk is not None for pk in calls)


async def test_slow_path_related_factory_fires_per_row(session):
    class ItemFactory(Factory[Item]):
        model = Item
        name = Sequence(lambda n: f"related-{n}")
        value = 0

    class AuthorFactory(Factory[Author]):
        model = Author
        email = Sequence(lambda n: f"e{n}@example.com")
        first_name = "Author"
        linked_item = RelatedFactory(
            ItemFactory, name=lambda inst: f"for-author-{inst.id}"
        )

    authors = await AuthorFactory.create_batch(session, 2)
    assert len(authors) == 2
    # Each author creation triggers one RelatedFactory → 2 items created
    await session.flush()
    from sqlalchemy import select

    result = await session.execute(select(Item).where(Item.name.like("for-author-%")))
    linked = result.scalars().all()
    assert len(linked) == 2


# ── fast path equivalence vs per-row ────────────────────────────────────────


async def test_fast_batch_equivalent_to_per_row_single_create(session):
    """Fast-batch instances must have the same shape as per-row create()."""

    class ItemFactory(Factory[Item]):
        model = Item
        name = "canonical"
        value = 42

    single = await ItemFactory.create(session)
    ItemFactory.reset_sequence()
    batch = await ItemFactory.create_batch(session, 1)

    assert single.name == batch[0].name
    assert single.value == batch[0].value
    assert single.id != batch[0].id  # distinct rows
