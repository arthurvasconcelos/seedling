from __future__ import annotations

from seedling import AutoFactory
from examples.fastapi_alembic.app.models import User


class UserFactory(AutoFactory[User]):
    model = User
