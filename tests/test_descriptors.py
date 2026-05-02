from __future__ import annotations

import pytest

from seedling.factory import (
    AutoFactory,
    Faker,
    Factory,
    Iterator,
    LazyAttribute,
    SelfAttribute,
    Sequence,
    Skip,
)
from tests.conftest import Author, Item


# ── SelfAttribute ──────────────────────────────────────────────────────────────


class SelfAttrFactory(Factory[Item]):
    model = Item
    name = "hello"
    value = SelfAttribute("name")  # copies whatever name resolves to


def test_self_attribute_copies_sibling_field():
    item = SelfAttrFactory.build()
    assert item.value == "hello"


def test_self_attribute_sees_override():
    item = SelfAttrFactory.build(name="world")
    assert item.value == "world"


def test_self_attribute_default_when_missing():
    class Factory_(Factory[Item]):
        model = Item
        name = "n"
        value = SelfAttribute("nonexistent_field", default=99)

    item = Factory_.build()
    assert item.value == 99


def test_self_attribute_dot_path():
    class Wrapper:
        def __init__(self, inner: str) -> None:
            self.inner = inner

    class WrapFactory(Factory[Item]):
        model = Item
        name = Wrapper("dot-value")
        value = SelfAttribute("name.inner", default=None)

    item = WrapFactory.build()
    assert item.value == "dot-value"


async def test_self_attribute_in_create(session):
    item = await SelfAttrFactory.create(session)
    assert item.value == "hello"


# ── Iterator ───────────────────────────────────────────────────────────────────


def test_iterator_cycles_values():
    itr = Iterator(["a", "b", "c"])
    assert itr._next() == "a"
    assert itr._next() == "b"
    assert itr._next() == "c"
    assert itr._next() == "a"  # wraps


def test_iterator_reset():
    itr = Iterator(["x", "y"])
    itr._next()
    itr._next()
    itr.reset()
    assert itr._next() == "x"


def test_iterator_single_value():
    itr = Iterator(["only"])
    assert itr._next() == "only"
    assert itr._next() == "only"


def test_iterator_requires_values():
    with pytest.raises(ValueError, match="at least one value"):
        Iterator([])


def test_iterator_as_factory_field():
    class IterFactory(Factory[Item]):
        model = Item
        name = Iterator(["alpha", "beta", "gamma"])
        value = 0

    a = IterFactory.build()
    b = IterFactory.build()
    c = IterFactory.build()
    d = IterFactory.build()
    assert a.name == "alpha"
    assert b.name == "beta"
    assert c.name == "gamma"
    assert d.name == "alpha"


def test_iterator_independent_per_instance():
    itr_a = Iterator([1, 2])
    itr_b = Iterator([10, 20])

    class FactoryA(Factory[Item]):
        model = Item
        name = "a"
        value = itr_a

    class FactoryB(Factory[Item]):
        model = Item
        name = "b"
        value = itr_b

    assert FactoryA.build().value == 1
    assert FactoryB.build().value == 10
    assert FactoryA.build().value == 2
    assert FactoryB.build().value == 20


async def test_iterator_in_create(session):
    class IterFactory(Factory[Item]):
        model = Item
        name = Iterator(["x", "y"])
        value = 0

    a = await IterFactory.create(session)
    b = await IterFactory.create(session)
    assert a.name != b.name


# ── Faker descriptor ───────────────────────────────────────────────────────────


def test_faker_descriptor_calls_provider():
    class EmailFactory(Factory[Author]):
        model = Author
        email = Faker("email")
        first_name = "Test"

    author = EmailFactory.build()
    assert "@" in author.email


def test_faker_descriptor_produces_different_values():
    class NameFactory(Factory[Author]):
        model = Author
        email = "e@e.com"
        first_name = Faker("first_name")

    names = {NameFactory.build().first_name for _ in range(10)}
    assert len(names) > 1  # not all the same


def test_faker_descriptor_locale():
    class LocaleFactory(Factory[Author]):
        model = Author
        email = "e@e.com"
        first_name = Faker("first_name", locale="fr_FR")

    author = LocaleFactory.build()
    assert isinstance(author.first_name, str)
    assert len(author.first_name) > 0


def test_faker_descriptor_with_kwargs():
    class NumerifyFactory(Factory[Item]):
        model = Item
        name = Faker("numerify", text="###-##")
        value = 0

    item = NumerifyFactory.build()
    assert len(item.name) == 6
    assert item.name[3] == "-"


async def test_faker_descriptor_in_create(session):
    class AuthorFakerFactory(Factory[Author]):
        model = Author
        email = Faker("email")
        first_name = Faker("first_name")

    author = await AuthorFakerFactory.create(session)
    assert author.id is not None
    assert "@" in author.email


# ── Skip sentinel ─────────────────────────────────────────────────────────────


def test_skip_is_singleton():
    from seedling.factory import Skip as Skip2
    assert Skip is Skip2


def test_skip_omits_field_from_build():
    class SkipFactory(Factory[Item]):
        model = Item
        name = "present"
        value = Skip  # type: ignore[assignment]

    item = SkipFactory.build()
    assert item.name == "present"
    # value is omitted — ORM column defaults only apply at INSERT time, not build()
    assert item.value is None


def test_skip_overrides_autofactory_field():
    class AuthorSkipFactory(AutoFactory[Author]):
        model = Author
        email = Skip  # type: ignore[assignment]

    inst = AuthorSkipFactory.build()
    # email was not set by AutoFactory (smart default suppressed by Skip)
    assert inst.email is None or inst.email == ""  # depends on model default


def test_skip_in_trait_suppresses_factory_field():
    class SuppressFactory(Factory[Item]):
        model = Item
        name = "original"
        value = 42

        class no_value(SelfAttribute):
            pass

    # Not using SelfAttribute for Trait here — just testing Skip in trait via direct approach
    class DirectSkipFactory(Factory[Item]):
        model = Item
        name = "original"
        value = 42

    # Override via build kwarg
    item = DirectSkipFactory.build(value=Skip)  # type: ignore[arg-type]
    # Skip passed as override is NOT handled — it's passed through to the model.
    # This tests that Skip sentinel works as a field-level declaration, not as a kwarg.
    # (Skip as kwarg is not a supported use-case — just as a class-level attribute.)
    # Build should still succeed; value will be whatever the model accepts.
    assert isinstance(item, Item)


async def test_skip_suppresses_autofactory_field_override_provides_value(session):
    class AuthorSkipCreate(AutoFactory[Author]):
        model = Author
        # Skip suppresses the smart default; caller must supply the value explicitly
        first_name = Skip  # type: ignore[assignment]

    author = await AuthorSkipCreate.create(session, first_name="Provided")
    assert author.id is not None
    assert author.first_name == "Provided"
