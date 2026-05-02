from __future__ import annotations

from seedling import AutoFactory
from examples.script.models import User


class UserFactory(AutoFactory[User]):
    model = User
