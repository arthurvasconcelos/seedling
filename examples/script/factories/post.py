from __future__ import annotations

from seedling import AutoFactory
from examples.script.models import Post


class PostFactory(AutoFactory[Post]):
    model = Post
    # author_id is auto-resolved by AutoFactory via the factory registry
