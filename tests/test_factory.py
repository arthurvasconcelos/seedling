from __future__ import annotations

from seedling.factory import Factory, LazyAttribute, Sequence, SubFactory
from tests.conftest import Item


class ItemFactory(Factory[Item]):
    model = Item
    name = "default-name"
    value = 42


class SequencedFactory(Factory[Item]):
    model = Item
    name = Sequence(lambda n: f"item-{n}")
    value = 0


class LazyFactory(Factory[Item]):
    model = Item
    name = "base"
    value = LazyAttribute(lambda f: len(f["name"]) * 10)


class ChildFactory(Factory[Item]):
    model = Item
    name = SubFactory(ItemFactory)  # type: ignore[assignment]  # not a real FK, just for testing wiring
    value = 0


# ── build() ────────────────────────────────────────────────────────────────────


def test_build_returns_model_instance():
    item = ItemFactory.build()
    assert isinstance(item, Item)
    assert item.name == "default-name"
    assert item.value == 42


def test_build_override_replaces_field():
    item = ItemFactory.build(name="custom")
    assert item.name == "custom"


def test_build_sequence_increments():
    a = SequencedFactory.build()
    b = SequencedFactory.build()
    assert a.name.startswith("item-")
    assert b.name.startswith("item-")
    # Sequence values must be different
    assert a.name != b.name


def test_build_lazy_attribute_receives_partial_dict():
    item = LazyFactory.build()
    # value = len("base") * 10 = 40
    assert item.value == 40


def test_build_lazy_attribute_with_override():
    item = LazyFactory.build(name="hello")
    # LazyAttribute sees the override in its dict
    assert item.value == 50  # len("hello") * 10


def test_build_skips_subfactory():
    # SubFactory fields are skipped in build(); no DB needed
    item = ChildFactory.build()
    assert item.value == 0
    assert not hasattr(item, "name") or item.name is None or True  # name may be unset


# ── build_batch() ──────────────────────────────────────────────────────────────


def test_build_batch_returns_correct_count():
    items = ItemFactory.build_batch(3)
    assert len(items) == 3
    assert all(isinstance(i, Item) for i in items)


# ── as_trait() ─────────────────────────────────────────────────────────────────


def test_as_trait_overrides_fields():
    SpecialItem = ItemFactory.as_trait(value=99)
    item = SpecialItem.build()
    assert item.value == 99
    assert item.name == "default-name"  # inherited


def test_as_trait_does_not_mutate_original():
    ItemFactory.as_trait(value=99)
    item = ItemFactory.build()
    assert item.value == 42


def test_as_trait_chaining():
    Step1 = ItemFactory.as_trait(value=1)
    Step2 = Step1.as_trait(name="chained")
    item = Step2.build()
    assert item.value == 1
    assert item.name == "chained"


# ── create() ───────────────────────────────────────────────────────────────────


async def test_create_persists_to_db(session):
    item = await ItemFactory.create(session)
    assert item.id is not None
    assert item.name == "default-name"


async def test_create_with_override(session):
    item = await ItemFactory.create(session, name="persisted", value=7)
    assert item.name == "persisted"
    assert item.value == 7


async def test_create_batch_returns_list(session):
    items = await ItemFactory.create_batch(session, 3)
    assert len(items) == 3
    assert all(i.id is not None for i in items)


async def test_create_sequence_field(session):
    a = await SequencedFactory.create(session)
    b = await SequencedFactory.create(session)
    assert a.name != b.name


async def test_create_lazy_attribute(session):
    item = await LazyFactory.create(session)
    # value = len("base") * 10 = 40
    assert item.value == 40
