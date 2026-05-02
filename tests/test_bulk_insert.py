from __future__ import annotations

from seedling.factory import Factory, Sequence, post_generation
from tests.conftest import Item


class ItemFactory(Factory[Item]):
    model = Item
    name = Sequence(lambda n: f"bulk-{n}")
    value = 0


# ── basic bulk behaviour ──────────────────────────────────────────────────────


async def test_bulk_inserts_correct_count(session):
    items = await ItemFactory.create_batch(session, 5, bulk=True)
    assert len(items) == 5


async def test_bulk_returns_orm_instances_with_ids(session):
    items = await ItemFactory.create_batch(session, 3, bulk=True)
    assert all(isinstance(i, Item) for i in items)
    assert all(i.id is not None for i in items)
    assert len({i.id for i in items}) == 3


async def test_bulk_ids_are_distinct(session):
    ItemFactory.reset_sequence(0)
    items = await ItemFactory.create_batch(session, 10, bulk=True)
    ids = [i.id for i in items]
    assert len(ids) == len(set(ids))


# ── data matches per-row path ─────────────────────────────────────────────────


async def test_bulk_data_consistent_with_per_row(session):
    class FixedFactory(Factory[Item]):
        model = Item
        name = "fixed"
        value = 7

    bulk_items = await FixedFactory.create_batch(session, 3, bulk=True)
    for item in bulk_items:
        assert item.name == "fixed"
        assert item.value == 7


async def test_bulk_overrides_applied(session):
    class NameFactory(Factory[Item]):
        model = Item
        name = "default"
        value = 0

    items = await NameFactory.create_batch(session, 2, bulk=True, name="override")
    assert all(i.name == "override" for i in items)


async def test_bulk_sequence_advances(session):
    ItemFactory.reset_sequence(0)
    items = await ItemFactory.create_batch(session, 3, bulk=True)
    names = [i.name for i in items]
    assert len(set(names)) == 3  # all distinct


# ── bulk=False is the default ─────────────────────────────────────────────────


async def test_default_bulk_false_unchanged(session):
    items = await ItemFactory.create_batch(session, 2)
    assert all(i.id is not None for i in items)


# ── post_generation does NOT fire in bulk mode ────────────────────────────────


async def test_bulk_skips_post_generation_hooks(session):
    calls: list[int] = []

    class HookedFactory(Factory[Item]):
        model = Item
        name = "hooked"
        value = 0

        @post_generation
        async def track(instance, sess):
            calls.append(instance.id)

    await HookedFactory.create_batch(session, 3, bulk=True)
    assert calls == []  # hooks did not fire


async def test_non_bulk_post_generation_still_fires(session):
    calls: list[int] = []

    class HookedFactory(Factory[Item]):
        model = Item
        name = "hooked"
        value = 0

        @post_generation
        async def track(instance, sess):
            calls.append(instance.id)

    await HookedFactory.create_batch(session, 2, bulk=False)
    assert len(calls) == 2


# ── count = 0 ────────────────────────────────────────────────────────────────


async def test_bulk_count_zero_returns_empty(session):
    items = await ItemFactory.create_batch(session, 0, bulk=True)
    assert items == []
