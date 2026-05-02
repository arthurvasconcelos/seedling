from __future__ import annotations

from sqlalchemy import select

from seedling.factory import (
    Factory,
    RelatedFactory,
    RelatedFactoryList,
    post_generation,
)
from tests.conftest import Article, Author

# ─── helpers ────────────────────────────────────────────────────────────────


class AuthorFactory(Factory[Author]):
    model = Author
    email = "a@example.com"
    first_name = "Author"


class ArticleFactory(Factory[Article]):
    model = Article
    title = "Default Title"
    author_id = 0  # overridden by caller


# ─── RelatedFactory basics ───────────────────────────────────────────────────


async def test_related_factory_creates_related_row(session):
    class WithArticleFactory(Factory[Author]):
        model = Author
        email = "a@example.com"
        first_name = "A"

        article = RelatedFactory(ArticleFactory, author_id=lambda inst: inst.id)

    author = await WithArticleFactory.create(session)
    result = await session.execute(
        select(Article).where(Article.author_id == author.id)
    )
    articles = result.scalars().all()
    assert len(articles) == 1
    assert articles[0].author_id == author.id


async def test_related_factory_callable_kwarg_receives_parent(session):
    received: list[int] = []

    class TrackingArticleFactory(Factory[Article]):
        model = Article
        title = "tracked"

        @post_generation
        async def record_author(instance, sess):
            received.append(instance.author_id)

    class WithTrackedArticle(Factory[Author]):
        model = Author
        email = "b@example.com"
        first_name = "B"

        article = RelatedFactory(TrackingArticleFactory, author_id=lambda inst: inst.id)

    author = await WithTrackedArticle.create(session)
    assert received == [author.id]


async def test_related_factory_literal_kwarg(session):
    class ItemWithLiteral(Factory[Author]):
        model = Author
        email = "c@example.com"
        first_name = "C"

        article = RelatedFactory(
            ArticleFactory, title="literal-title", author_id=lambda inst: inst.id
        )

    author = await ItemWithLiteral.create(session)
    result = await session.execute(
        select(Article).where(Article.author_id == author.id)
    )
    article = result.scalars().first()
    assert article is not None
    assert article.title == "literal-title"


def test_related_factory_skipped_in_build():
    class WithArticleFactory(Factory[Author]):
        model = Author
        email = "d@example.com"
        first_name = "D"

        article = RelatedFactory(ArticleFactory, author_id=lambda inst: inst.id)

    inst = WithArticleFactory.build()
    assert isinstance(inst, Author)


async def test_related_factory_does_not_set_attribute_on_parent(session):
    class WithArticle(Factory[Author]):
        model = Author
        email = "e@example.com"
        first_name = "E"

        related_article = RelatedFactory(ArticleFactory, author_id=lambda inst: inst.id)

    author = await WithArticle.create(session)
    assert not hasattr(author, "related_article")


# ─── RelatedFactoryList ───────────────────────────────────────────────────────


async def test_related_factory_list_creates_n_rows(session):
    class WithArticles(Factory[Author]):
        model = Author
        email = "f@example.com"
        first_name = "F"

        articles = RelatedFactoryList(
            ArticleFactory, size=3, author_id=lambda inst: inst.id
        )

    author = await WithArticles.create(session)
    result = await session.execute(
        select(Article).where(Article.author_id == author.id)
    )
    rows = result.scalars().all()
    assert len(rows) == 3
    assert all(r.author_id == author.id for r in rows)


async def test_related_factory_list_size_zero_creates_nothing(session):
    class WithNoArticles(Factory[Author]):
        model = Author
        email = "g@example.com"
        first_name = "G"

        articles = RelatedFactoryList(
            ArticleFactory, size=0, author_id=lambda inst: inst.id
        )

    author = await WithNoArticles.create(session)
    result = await session.execute(
        select(Article).where(Article.author_id == author.id)
    )
    assert result.scalars().all() == []


async def test_related_factory_list_size_one_default(session):
    class WithOneArticle(Factory[Author]):
        model = Author
        email = "h@example.com"
        first_name = "H"

        articles = RelatedFactoryList(ArticleFactory, author_id=lambda inst: inst.id)

    author = await WithOneArticle.create(session)
    result = await session.execute(
        select(Article).where(Article.author_id == author.id)
    )
    assert len(result.scalars().all()) == 1


# ─── multiple RelatedFactories on one factory ────────────────────────────────


async def test_multiple_related_factories_all_fire(session):
    class WithTwo(Factory[Author]):
        model = Author
        email = "i@example.com"
        first_name = "I"

        first_article = RelatedFactory(
            ArticleFactory, title="first", author_id=lambda inst: inst.id
        )
        more_articles = RelatedFactoryList(
            ArticleFactory, size=2, title="extra", author_id=lambda inst: inst.id
        )

    author = await WithTwo.create(session)
    result = await session.execute(
        select(Article).where(Article.author_id == author.id)
    )
    rows = result.scalars().all()
    assert len(rows) == 3


# ─── ordering: post_generation fires before related factories ─────────────────


async def test_post_generation_fires_before_related_factories(session):
    order: list[str] = []

    class TrackingArticle(Factory[Article]):
        model = Article
        title = "tracked"

        @post_generation
        async def record(instance, sess):
            order.append("related")

    class WithOrdering(Factory[Author]):
        model = Author
        email = "j@example.com"
        first_name = "J"

        @post_generation
        async def mark_parent(instance, sess):
            order.append("parent_hook")

        article = RelatedFactory(TrackingArticle, author_id=lambda inst: inst.id)

    await WithOrdering.create(session)
    assert order == ["parent_hook", "related"]


# ─── inheritance ─────────────────────────────────────────────────────────────


async def test_related_factory_inherited_from_parent(session):
    class BaseAuthorFactory(Factory[Author]):
        model = Author
        email = "k@example.com"
        first_name = "K"

        article = RelatedFactory(ArticleFactory, author_id=lambda inst: inst.id)

    class ChildAuthorFactory(BaseAuthorFactory):
        pass

    author = await ChildAuthorFactory.create(session)
    result = await session.execute(
        select(Article).where(Article.author_id == author.id)
    )
    assert len(result.scalars().all()) == 1
