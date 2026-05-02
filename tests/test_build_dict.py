from __future__ import annotations

from seedling.factory import (
    AutoFactory,
    Factory,
    LazyAttribute,
    Sequence,
    SubFactory,
    Trait,
)
from tests.conftest import Author, Item


class ItemFactory(Factory[Item]):
    model = Item
    name = "default"
    value = 42


class SeqFactory(Factory[Item]):
    model = Item
    name = Sequence(lambda n: f"item-{n}")
    value = 0


class LazyFactory(Factory[Item]):
    model = Item
    name = "base"
    value = LazyAttribute(lambda f: len(f["name"]) * 10)


# ── basic return type and values ──────────────────────────────────────────────


def test_build_dict_returns_dict():
    result = ItemFactory.build_dict()
    assert isinstance(result, dict)


def test_build_dict_contains_field_values():
    result = ItemFactory.build_dict()
    assert result["name"] == "default"
    assert result["value"] == 42


def test_build_dict_does_not_contain_id():
    result = ItemFactory.build_dict()
    assert "id" not in result


def test_build_dict_override_reflected():
    result = ItemFactory.build_dict(name="custom", value=7)
    assert result["name"] == "custom"
    assert result["value"] == 7


# ── descriptors work inside build_dict ────────────────────────────────────────


def test_build_dict_sequence():
    SeqFactory.reset_sequence(0)
    a = SeqFactory.build_dict()
    b = SeqFactory.build_dict()
    assert a["name"] == "item-0"
    assert b["name"] == "item-1"


def test_build_dict_lazy_attribute():
    result = LazyFactory.build_dict()
    assert result["value"] == 40  # len("base") * 10


def test_build_dict_lazy_attribute_with_override():
    result = LazyFactory.build_dict(name="hello")
    assert result["value"] == 50  # len("hello") * 10


# ── traits apply in build_dict ────────────────────────────────────────────────


def test_build_dict_with_trait():
    class TraitFactory(Factory[Item]):
        model = Item
        name = "original"
        value = 0

        class premium(Trait):
            value = 999

    result = TraitFactory.build_dict(premium=True)
    assert result["value"] == 999
    assert result["name"] == "original"


# ── SubFactory fields are absent (same as build) ─────────────────────────────


def test_build_dict_omits_subfactory_fields():
    class ParentFactory(Factory[Item]):
        model = Item
        name = SubFactory(ItemFactory)  # type: ignore[assignment]
        value = 0

    result = ParentFactory.build_dict()
    assert "name" not in result


# ── AutoFactory works with build_dict ────────────────────────────────────────


def test_build_dict_autofactory():
    class AuthorAutoFactory(AutoFactory[Author]):
        model = Author

    result = AuthorAutoFactory.build_dict()
    assert isinstance(result, dict)
    assert "@" in result["email"]
    assert isinstance(result["first_name"], str)
    assert "id" not in result


# ── result is a fresh copy each call ─────────────────────────────────────────


def test_build_dict_returns_independent_copies():
    a = ItemFactory.build_dict()
    b = ItemFactory.build_dict()
    a["name"] = "mutated"
    assert b["name"] == "default"
