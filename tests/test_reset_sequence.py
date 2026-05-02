from __future__ import annotations

from seedling.factory import Factory, Iterator, Sequence
from tests.conftest import Item


class SeqFactory(Factory[Item]):
    model = Item
    name = Sequence(lambda n: f"item-{n}")
    value = 0


class IterFactory(Factory[Item]):
    model = Item
    name = Iterator(["a", "b", "c"])
    value = 0


# ── reset_sequence resets Sequence counter ────────────────────────────────────


def test_reset_sequence_restarts_at_zero():
    SeqFactory.reset_sequence()
    first = SeqFactory.build()
    assert first.name == "item-0"


def test_reset_sequence_custom_start_value():
    SeqFactory.reset_sequence(10)
    item = SeqFactory.build()
    assert item.name == "item-10"


def test_reset_sequence_increments_continue_after_reset():
    SeqFactory.reset_sequence(0)
    a = SeqFactory.build()
    b = SeqFactory.build()
    assert a.name == "item-0"
    assert b.name == "item-1"


def test_reset_sequence_isolates_between_factories():
    class OtherFactory(Factory[Item]):
        model = Item
        name = Sequence(lambda n: f"other-{n}")
        value = 0

    SeqFactory.reset_sequence(0)
    OtherFactory.reset_sequence(0)

    SeqFactory.build()
    SeqFactory.build()

    OtherFactory.reset_sequence(0)
    other = OtherFactory.build()
    assert other.name == "other-0"

    # SeqFactory counter is unaffected
    seq = SeqFactory.build()
    assert seq.name == "item-2"


# ── reset_sequence also resets Iterator fields ────────────────────────────────


def test_reset_sequence_resets_iterator():
    IterFactory.reset_sequence()
    a = IterFactory.build()
    b = IterFactory.build()
    assert a.name == "a"
    assert b.name == "b"

    IterFactory.reset_sequence()
    c = IterFactory.build()
    assert c.name == "a"  # restarted


def test_reset_sequence_resets_iterator_in_mro():
    class ParentFactory(Factory[Item]):
        model = Item
        name = Iterator(["x", "y"])
        value = 0

    class ChildFactory(ParentFactory):
        pass

    ChildFactory.build()  # advances to "x"
    ChildFactory.build()  # advances to "y"

    ChildFactory.reset_sequence()
    item = ChildFactory.build()
    assert item.name == "x"  # Iterator in parent was reset


# ── async: reset before each test in create ──────────────────────────────────


async def test_reset_sequence_before_create(session):
    SeqFactory.reset_sequence(0)
    item = await SeqFactory.create(session)
    assert item.name == "item-0"
