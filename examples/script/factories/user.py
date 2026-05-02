from __future__ import annotations

from examples.script.models import User
from seedling import AutoFactory


class UserFactory(AutoFactory[User]):
    model = User
