from __future__ import annotations

import inspect
from collections.abc import Callable
from typing import Any, ClassVar, Generic, TypeVar

from faker import Faker
from sqlalchemy.ext.asyncio import AsyncSession

T = TypeVar("T")

faker = Faker()

_sequence_counters: dict[type, int] = {}
_RESERVED = frozenset({"model"})


class LazyAttribute:
    """Callable evaluated once per instance build, receiving the partial field dict."""

    def __init__(self, func: Callable[[dict[str, Any]], Any]) -> None:
        self.func = func


class Sequence:
    """Auto-incrementing counter per factory class."""

    def __init__(self, func: Callable[[int], Any]) -> None:
        self.func = func


class SubFactory:
    """Delegates field creation to another factory (async, creates a DB row)."""

    def __init__(self, factory: type[Factory]) -> None:
        self.factory = factory


class Factory(Generic[T]):
    model: ClassVar[type]

    @classmethod
    def _get_declared_fields(cls) -> dict[str, Any]:
        """Walk MRO (base → subclass) to collect field declarations."""
        fields: dict[str, Any] = {}
        for klass in reversed(cls.__mro__):
            if klass in (Factory, object):
                continue
            for name, value in vars(klass).items():
                if name.startswith("_"):
                    continue
                if name in _RESERVED:
                    continue
                if isinstance(value, (classmethod, staticmethod)):
                    continue
                if inspect.isfunction(value):
                    continue
                fields[name] = value
        return fields

    @classmethod
    def _next_sequence(cls) -> int:
        _sequence_counters[cls] = _sequence_counters.get(cls, -1) + 1
        return _sequence_counters[cls]

    @classmethod
    def build(cls, **overrides: Any) -> T:
        """Build an instance without DB interaction. SubFactory fields are skipped."""
        fields = cls._get_declared_fields()
        built: dict[str, Any] = {}

        for name, descriptor in fields.items():
            if name in overrides or isinstance(descriptor, SubFactory):
                continue
            if not isinstance(descriptor, (LazyAttribute, Sequence)):
                built[name] = descriptor

        for name, descriptor in fields.items():
            if name in overrides or isinstance(descriptor, SubFactory):
                continue
            if isinstance(descriptor, LazyAttribute):
                built[name] = descriptor.func({**built, **overrides})

        for name, descriptor in fields.items():
            if name in overrides or isinstance(descriptor, SubFactory):
                continue
            if isinstance(descriptor, Sequence):
                built[name] = descriptor.func(cls._next_sequence())

        built.update(overrides)
        return cls.model(**built)  # type: ignore[no-any-return]

    @classmethod
    def build_batch(cls, count: int, **overrides: Any) -> list[T]:
        return [cls.build(**overrides) for _ in range(count)]

    @classmethod
    async def create(cls, session: AsyncSession, **overrides: Any) -> T:
        """Build and persist an instance. Caller is responsible for committing."""
        fields = cls._get_declared_fields()
        built: dict[str, Any] = {}

        # 1. Literals
        for name, descriptor in fields.items():
            if name in overrides:
                continue
            if not isinstance(descriptor, (LazyAttribute, Sequence, SubFactory)):
                built[name] = descriptor

        # 2. SubFactories (async — each may insert a row)
        for name, descriptor in fields.items():
            if name in overrides:
                continue
            if isinstance(descriptor, SubFactory):
                built[name] = await descriptor.factory.create(session)

        # 3. LazyAttributes (receive partially-built dict)
        for name, descriptor in fields.items():
            if name in overrides:
                continue
            if isinstance(descriptor, LazyAttribute):
                built[name] = descriptor.func({**built, **overrides})

        # 4. Sequences
        for name, descriptor in fields.items():
            if name in overrides:
                continue
            if isinstance(descriptor, Sequence):
                built[name] = descriptor.func(cls._next_sequence())

        # 5. Overrides replace any computed value
        built.update(overrides)

        instance = cls.model(**built)
        session.add(instance)
        await session.flush()
        await session.refresh(instance)
        return instance  # type: ignore[no-any-return]

    @classmethod
    async def create_batch(
        cls, session: AsyncSession, count: int, **overrides: Any
    ) -> list[T]:
        return [await cls.create(session, **overrides) for _ in range(count)]

    @classmethod
    def as_trait(cls, **trait_overrides: Any) -> type[Factory[T]]:
        """Return a subclass with trait overrides pre-applied."""
        return type(f"{cls.__name__}(trait)", (cls,), trait_overrides)
