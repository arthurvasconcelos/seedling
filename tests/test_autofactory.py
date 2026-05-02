from __future__ import annotations

import pytest

from seedling.exceptions import AutoFactoryResolutionError
from seedling.factory import AutoFactory, LazyAttribute, _clear_registry
from tests.conftest import Article, Author, Item

# ── fixtures ───────────────────────────────────────────────────────────────────


@pytest.fixture(autouse=False)
def isolated_registry():
    from seedling.factory import _registry

    snapshot = dict(_registry)
    yield
    _registry.clear()
    _registry.update(snapshot)


# ── basic introspection ────────────────────────────────────────────────────────


def test_autofactory_generates_fields_without_declaration():
    class ItemAutoFactory(AutoFactory[Item]):
        model = Item

    inst = ItemAutoFactory.build()
    assert isinstance(inst, Item)
    assert inst.name is not None
    assert inst.value is not None


def test_autofactory_skips_primary_key():
    class ItemAutoFactory(AutoFactory[Item]):
        model = Item

    inst = ItemAutoFactory.build()
    # id is a PK — AutoFactory must not set it (stays None before DB flush)
    assert inst.id is None


def test_autofactory_string_field_produces_unique_values():
    class ItemAutoFactory(AutoFactory[Item]):
        model = Item

    a = ItemAutoFactory.build()
    b = ItemAutoFactory.build()
    assert a.name != b.name


def test_autofactory_integer_field_produces_values():
    class ItemAutoFactory(AutoFactory[Item]):
        model = Item

    inst = ItemAutoFactory.build()
    assert isinstance(inst.value, int)


# ── smart defaults ─────────────────────────────────────────────────────────────


def test_autofactory_smart_default_email(isolated_registry):
    class AuthorAutoFactory(AutoFactory[Author]):
        model = Author

    inst = AuthorAutoFactory.build()
    assert "@" in inst.email


def test_autofactory_smart_default_first_name(isolated_registry):
    class AuthorAutoFactory(AutoFactory[Author]):
        model = Author

    inst = AuthorAutoFactory.build()
    assert isinstance(inst.first_name, str)
    assert len(inst.first_name) > 0


def test_autofactory_smart_defaults_disabled(isolated_registry):
    class AuthorNoSmartFactory(AutoFactory[Author]):
        model = Author

        class Meta:
            smart_defaults = False

    inst = AuthorNoSmartFactory.build()
    # With smart_defaults off, email gets Sequence("value-N") — no "@" guaranteed
    assert isinstance(inst.email, str)
    # Should not contain "@" since faker.email() was not used
    assert "@" not in inst.email


# ── explicit field overrides declared fields win ───────────────────────────────


def test_autofactory_declared_field_overrides_auto():
    class ItemCustomFactory(AutoFactory[Item]):
        model = Item
        name = "fixed-name"

    inst = ItemCustomFactory.build()
    assert inst.name == "fixed-name"


def test_autofactory_declared_lazy_attribute_overrides_auto():
    class ItemLazyFactory(AutoFactory[Item]):
        model = Item
        value = LazyAttribute(lambda f: 999)

    inst = ItemLazyFactory.build()
    assert inst.value == 999


def test_autofactory_build_override_kwarg_wins():
    class ItemAutoFactory(AutoFactory[Item]):
        model = Item

    inst = ItemAutoFactory.build(name="kwarg-wins")
    assert inst.name == "kwarg-wins"


# ── FK resolution ──────────────────────────────────────────────────────────────


async def test_autofactory_fk_resolved_via_registry(isolated_registry, session):
    class AuthorFactory(AutoFactory[Author]):
        model = Author

    class ArticleFactory(AutoFactory[Article]):
        model = Article

    article = await ArticleFactory.create(session)
    assert article.id is not None
    assert isinstance(article.author_id, int)
    assert article.author_id > 0


async def test_autofactory_nullable_fk_skipped_when_no_factory(
    isolated_registry, session
):
    # With an empty registry, editor_id (nullable FK → authors) must be skipped
    # (left None). author_id is non-nullable so we supply it as an override to
    # avoid triggering AutoFactoryResolutionError for that column.
    _clear_registry()

    author = Author(email="direct@example.com", first_name="Direct")
    session.add(author)
    await session.flush()
    await session.refresh(author)

    class ArticleNullEditorFactory(AutoFactory[Article]):
        model = Article

    article = await ArticleNullEditorFactory.create(session, author_id=author.id)
    assert article.editor_id is None


async def test_autofactory_nonnullable_fk_raises_when_no_factory(
    isolated_registry, session
):
    _clear_registry()

    class ArticleOrphanFactory(AutoFactory[Article]):
        model = Article

    with pytest.raises(AutoFactoryResolutionError, match="author_id"):
        await ArticleOrphanFactory.create(session)


async def test_autofactory_fk_override_bypasses_resolution(isolated_registry, session):
    _clear_registry()

    class ArticleOverrideFactory(AutoFactory[Article]):
        model = Article

    # Manually create an Author so we can pass author_id= explicitly
    from tests.conftest import Author as AuthorModel

    author = AuthorModel(email="x@x.com", first_name="X")
    session.add(author)
    await session.flush()
    await session.refresh(author)

    article = await ArticleOverrideFactory.create(session, author_id=author.id)
    assert article.author_id == author.id


# ── build() skips all FK descriptors ──────────────────────────────────────────


def test_autofactory_build_skips_fk_fields(isolated_registry):
    class AuthorFactory(AutoFactory[Author]):
        model = Author

    class ArticleFactory(AutoFactory[Article]):
        model = Article

    # build() must not attempt to create related rows
    inst = ArticleFactory.build()
    # author_id may be unset (None) — that's fine for an in-memory build
    assert isinstance(inst, Article)


# ── create() persists correctly ────────────────────────────────────────────────


async def test_autofactory_create_persists(isolated_registry, session):
    class AuthorFactory(AutoFactory[Author]):
        model = Author

    author = await AuthorFactory.create(session)
    assert author.id is not None
    assert "@" in author.email


async def test_autofactory_create_batch(isolated_registry, session):
    class AuthorFactory(AutoFactory[Author]):
        model = Author

    authors = await AuthorFactory.create_batch(session, 3)
    assert len(authors) == 3
    assert len({a.id for a in authors}) == 3
