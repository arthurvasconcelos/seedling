from __future__ import annotations

from examples.fastapi_alembic.app.models import User
from seedling import AutoFactory


class UserFactory(AutoFactory[User]):
    model = User
