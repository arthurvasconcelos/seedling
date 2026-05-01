"""Factories for the smoke test models."""

from __future__ import annotations

from seedling import Factory, LazyAttribute, Sequence, SubFactory, faker

from .models import Post, User


class UserFactory(Factory[User]):
    model = User
    email = LazyAttribute(lambda f: faker.unique.email())
    name = Sequence(lambda n: f"User {n}")


class PostFactory(Factory[Post]):
    model = Post
    author = SubFactory(UserFactory)
    title = LazyAttribute(lambda f: faker.sentence(nb_words=4))
