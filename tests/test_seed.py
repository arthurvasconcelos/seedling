from __future__ import annotations

from seedling.factory import Factory, Faker
from tests.conftest import Author, Item


class AuthorFakerFactory(Factory[Author]):
    model = Author
    email = Faker("email")
    first_name = Faker("first_name")


# ── seeded output is deterministic ────────────────────────────────────────────


def test_seed_produces_same_values_on_repeat():
    AuthorFakerFactory.seed(42)
    a = AuthorFakerFactory.build()

    AuthorFakerFactory.seed(42)
    b = AuthorFakerFactory.build()

    assert a.email == b.email
    assert a.first_name == b.first_name


def test_different_seeds_produce_different_values():
    AuthorFakerFactory.seed(1)
    a = AuthorFakerFactory.build()

    AuthorFakerFactory.seed(999)
    b = AuthorFakerFactory.build()

    # Different seeds should (with overwhelming probability) give different values
    assert a.email != b.email or a.first_name != b.first_name


def test_seed_applies_to_module_level_faker():
    class NameFactory(Factory[Item]):
        model = Item
        name = Faker("word")
        value = 0

    NameFactory.seed(7)
    x = NameFactory.build().name

    NameFactory.seed(7)
    y = NameFactory.build().name

    assert x == y


def test_seed_applies_to_localized_faker():
    class LocalFactory(Factory[Author]):
        model = Author
        email = "e@e.com"
        first_name = Faker("first_name", locale="fr_FR")

    # Trigger creation of the localized instance
    LocalFactory.build()

    LocalFactory.seed(42)
    a = LocalFactory.build().first_name

    LocalFactory.seed(42)
    b = LocalFactory.build().first_name

    assert a == b


async def test_seed_deterministic_in_create(session):
    AuthorFakerFactory.seed(42)
    a = await AuthorFakerFactory.create(session)

    AuthorFakerFactory.seed(42)
    b = await AuthorFakerFactory.create(session)

    assert a.email == b.email
