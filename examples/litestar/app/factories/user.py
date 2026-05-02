from __future__ import annotations

from examples.litestar.app.models import User
from seedling import AutoFactory


class UserFactory(AutoFactory[User]):
    model = User
