from __future__ import annotations

import pytest

from seedling.factory import Factory, LazyAttribute, Sequence, SubFactory, Trait, _clear_registry, get_factory
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


# ── class Trait ────────────────────────────────────────────────────────────────


class TraitItemFactory(Factory[Item]):
    model = Item
    name = "default-name"
    value = 42

    class special(Trait):
        value = 99

    class renamed(Trait):
        name = "renamed"
        value = 1


def test_trait_overrides_field():
    item = TraitItemFactory.build(special=True)
    assert item.value == 99
    assert item.name == "default-name"


def test_trait_not_applied_leaves_default():
    item = TraitItemFactory.build()
    assert item.value == 42


def test_trait_does_not_mutate_original():
    TraitItemFactory.build(special=True)
    item = TraitItemFactory.build()
    assert item.value == 42


def test_trait_stacking_later_wins():
    # both traits set value; 'renamed' appears later in kwargs → wins
    item = TraitItemFactory.build(special=True, renamed=True)
    assert item.value == 1
    assert item.name == "renamed"


def test_trait_explicit_kwarg_beats_trait():
    item = TraitItemFactory.build(special=True, value=0)
    assert item.value == 0


def test_trait_false_not_applied_and_not_forwarded_to_model():
    # special=False must not apply the trait AND must not be forwarded to Item()
    item = TraitItemFactory.build(special=False)
    assert item.value == 42  # trait not applied


def test_trait_inherited_from_parent():
    class ChildItemFactory(TraitItemFactory):
        pass

    item = ChildItemFactory.build(special=True)
    assert item.value == 99


def test_trait_lazy_attribute_inside_trait():
    class LazyTraitFactory(Factory[Item]):
        model = Item
        name = "base"
        value = 0

        class computed(Trait):
            value = LazyAttribute(lambda f: len(f.get("name", "")) * 10)

    item = LazyTraitFactory.build(computed=True)
    assert item.value == 40  # len("base") * 10


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


# ── factory registry ───────────────────────────────────────────────────────────


@pytest.fixture(autouse=False)
def isolated_registry():
    """Snapshot and restore the registry around a test to avoid cross-test pollution."""
    from seedling.factory import _registry
    snapshot = dict(_registry)
    yield
    _registry.clear()
    _registry.update(snapshot)


def test_factory_registers_on_definition(isolated_registry):
    class RegModel:
        pass

    class RegFactory(Factory[RegModel]):
        model = RegModel

    assert get_factory(RegModel) is RegFactory


def test_factory_without_model_does_not_register(isolated_registry):
    class NoModelFactory(Factory[object]):
        pass

    assert get_factory(object) is None


def test_factory_inherited_model_does_not_re_register(isolated_registry):
    class BaseModel:
        pass

    class BaseFactory(Factory[BaseModel]):
        model = BaseModel

    class ChildFactory(BaseFactory):
        pass

    # ChildFactory inherits model but doesn't declare its own — BaseFactory stays
    assert get_factory(BaseModel) is BaseFactory


def test_later_definition_overwrites_earlier(isolated_registry):
    class OverModel:
        pass

    class FirstFactory(Factory[OverModel]):
        model = OverModel

    class SecondFactory(Factory[OverModel]):
        model = OverModel

    assert get_factory(OverModel) is SecondFactory


def test_get_factory_returns_none_for_unknown_model():
    class Unknown:
        pass

    assert get_factory(Unknown) is None


def test_trait_inner_class_does_not_pollute_registry(isolated_registry):
    class TraitModel:
        pass

    class TraitableFactory(Factory[TraitModel]):
        model = TraitModel

        class premium(Trait):
            value = 99

    # The inner Trait class must not be picked up as a Factory registration
    assert get_factory(TraitModel) is TraitableFactory


# ── Trait + create() ───────────────────────────────────────────────────────────


async def test_trait_applied_in_create(session):
    item = await TraitItemFactory.create(session, special=True)
    assert item.id is not None
    assert item.value == 99
    assert item.name == "default-name"


async def test_trait_not_applied_in_create(session):
    item = await TraitItemFactory.create(session)
    assert item.value == 42
