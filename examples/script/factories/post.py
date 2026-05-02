from __future__ import annotations

from examples.script.models import Post
from seedling import AutoFactory


class PostFactory(AutoFactory[Post]):
    model = Post
    # author_id is auto-resolved by AutoFactory via the factory registry
