from __future__ import annotations

import datetime as _dt
import inspect
import uuid as _uuid
from collections.abc import Callable
from typing import Any, ClassVar, Generic, TypeVar, cast

from faker import Faker as _FakerLib
from sqlalchemy import insert as sa_insert
from sqlalchemy import inspect as sa_inspect
from sqlalchemy import types as sa_types
from sqlalchemy.ext.asyncio import AsyncSession

T = TypeVar("T")

faker = _FakerLib()

_sequence_counters: dict[type, int] = {}
_registry: dict[type, type[Factory[Any]]] = {}
_RESERVED = frozenset({"model", "Meta"})

_NAME_HEURISTICS: dict[str, Callable[[], Any]] = {
    "email": lambda: faker.email(),
    "phone": lambda: faker.phone_number(),
    "phone_number": lambda: faker.phone_number(),
    "first_name": lambda: faker.first_name(),
    "last_name": lambda: faker.last_name(),
    "full_name": lambda: faker.name(),
    "name": lambda: faker.name(),
    "username": lambda: faker.user_name(),
    "user_name": lambda: faker.user_name(),
    "password": lambda: faker.password(),
    "address": lambda: faker.address(),
    "street_address": lambda: faker.street_address(),
    "city": lambda: faker.city(),
    "state": lambda: faker.state(),
    "country": lambda: faker.country(),
    "zip_code": lambda: faker.postcode(),
    "postal_code": lambda: faker.postcode(),
    "url": lambda: faker.url(),
    "website": lambda: faker.url(),
    "description": lambda: faker.sentence(),
    "bio": lambda: faker.paragraph(),
    "title": lambda: faker.sentence(nb_words=4),
    "slug": lambda: faker.slug(),
    "ip_address": lambda: faker.ipv4(),
    "company": lambda: faker.company(),
    "company_name": lambda: faker.company(),
}


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


class SelfAttribute:
    """Reference another field that was already built in the same factory call.

    ``attr_path`` may use dot notation to traverse an attribute of the resolved
    value (e.g. ``"user.email"``).  ``default`` is returned when the field is
    not yet available (e.g. skipped by a SubFactory in ``build()``).
    """

    def __init__(self, attr_path: str, default: Any = None) -> None:
        self.attr_path = attr_path
        self.default = default


class Iterator:
    """Cycle through a fixed sequence of values, advancing by one per instance built.

    Resets when ``reset_sequence()`` is called on the owning factory.
    """

    def __init__(self, values: list[Any]) -> None:
        if not values:
            raise ValueError("Iterator requires at least one value")
        self.values = list(values)
        self._idx = 0

    def _next(self) -> Any:
        val = self.values[self._idx % len(self.values)]
        self._idx += 1
        return val

    def reset(self) -> None:
        self._idx = 0


class Faker:
    """Call a faker provider by name each time an instance is built.

    Optional ``locale`` creates a locale-specific faker instance.  Any
    additional positional or keyword arguments are forwarded to the provider::

        email   = Faker("email")
        name    = Faker("name", locale="fr_FR")
        digits  = Faker("numerify", text="###-##")
    """

    def __init__(
        self,
        provider: str,
        *args: Any,
        locale: str | None = None,
        **kwargs: Any,
    ) -> None:
        self.provider = provider
        self.args = args
        self.locale = locale
        self.kwargs = kwargs
        self._localized: _FakerLib | None = None

    def generate(self) -> Any:
        if self.locale is None:
            return getattr(faker, self.provider)(*self.args, **self.kwargs)
        if self._localized is None:
            self._localized = _FakerLib(self.locale)
        return getattr(self._localized, self.provider)(*self.args, **self.kwargs)


class _SkipType:
    """Singleton sentinel: tells a factory to omit a field entirely.

    Use the module-level ``Skip`` constant rather than instantiating this
    class directly.
    """

    _instance: _SkipType | None = None

    def __new__(cls) -> _SkipType:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __repr__(self) -> str:
        return "Skip"


Skip: _SkipType = _SkipType()
"""Sentinel that tells a factory to omit a field entirely.

Useful in AutoFactory subclasses to suppress an auto-generated field::

    class UserFactory(AutoFactory[User]):
        model = User
        sensitive_column = Skip
"""


class _FKSubFactory:
    """Internal descriptor: creates a related row via a factory and returns its PK value."""

    def __init__(self, factory: type[Factory[Any]]) -> None:
        self.factory = factory


class _UnresolvableFK:
    """Internal descriptor: placeholder for a non-nullable FK with no registered factory.
    Raises AutoFactoryResolutionError at create() time."""

    def __init__(self, col_name: str, target_table: str, factory_name: str) -> None:
        self.col_name = col_name
        self.target_table = target_table
        self.factory_name = factory_name


class post_generation:
    """Decorator for async post-generation hooks.

    The decorated function is called after the instance has been flushed and
    refreshed in ``create()``.  It is silently skipped in ``build()``.

    Signature::

        class UserFactory(Factory[User]):
            @post_generation
            async def setup(instance, session):
                await ProfileFactory.create(session, user_id=instance.id)

    Sync functions are also accepted; they are called without ``await``.
    """

    def __init__(self, func: Callable[..., Any]) -> None:
        self.func = func
        self.__name__ = func.__name__


class RelatedFactory:
    """Declare as a factory attribute to create one related instance after the main
    instance is persisted.

    Keyword arguments are forwarded to the related factory's ``create()``.
    Callable kwargs receive the parent instance and are called to produce the value::

        class AuthorFactory(Factory[Author]):
            default_article = RelatedFactory(
                ArticleFactory,
                author_id=lambda inst: inst.id,
            )

    The related object is created after ``@post_generation`` hooks fire.
    Silently skipped in ``build()``.
    """

    def __init__(self, factory: type[Factory[Any]], **kwargs: Any) -> None:
        self.factory = factory
        self.kwargs = kwargs

    async def generate(self, instance: Any, session: AsyncSession) -> Any:
        resolved = {
            k: (v(instance) if callable(v) else v) for k, v in self.kwargs.items()
        }
        return await self.factory.create(session, **resolved)


class RelatedFactoryList:
    """Like ``RelatedFactory`` but creates *size* related instances.

    class AuthorFactory(Factory[Author]):
        articles = RelatedFactoryList(
            ArticleFactory,
            size=3,
            author_id=lambda inst: inst.id,
        )
    """

    def __init__(
        self, factory: type[Factory[Any]], size: int = 1, **kwargs: Any
    ) -> None:
        self.factory = factory
        self.size = size
        self.kwargs = kwargs

    async def generate(self, instance: Any, session: AsyncSession) -> list[Any]:
        resolved = {
            k: (v(instance) if callable(v) else v) for k, v in self.kwargs.items()
        }
        return [
            await self.factory.create(session, **resolved) for _ in range(self.size)
        ]


class Trait:
    """Base class for declarative factory traits.

    Define as an inner class of a Factory.  Apply via bool kwargs at call time::

        class UserFactory(Factory[User]):
            is_staff = False

            class admin(Trait):
                is_staff = True

        await UserFactory.create(session, admin=True)

    Multiple traits stack left-to-right; later traits win on conflicts.
    Explicit kwargs always beat trait fields.
    """


def _collect_trait_fields(trait_cls: type) -> dict[str, Any]:
    """Return the field declarations of a Trait subclass."""
    _non_fields = post_generation | RelatedFactory | RelatedFactoryList
    fields: dict[str, Any] = {}
    for name, value in vars(trait_cls).items():
        if name.startswith("_"):
            continue
        if isinstance(value, classmethod | staticmethod):
            continue
        if inspect.isfunction(value):
            continue
        if inspect.isclass(value):
            continue
        if isinstance(value, _non_fields):
            continue
        fields[name] = value
    return fields


class Factory(Generic[T]):
    model: ClassVar[type]

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        model = cls.__dict__.get("model")
        if model is not None:
            _registry[model] = cls

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
                if isinstance(value, classmethod | staticmethod):
                    continue
                if inspect.isfunction(value):
                    continue
                if inspect.isclass(value):
                    continue
                if isinstance(
                    value, post_generation | RelatedFactory | RelatedFactoryList
                ):
                    continue
                fields[name] = value
        return fields

    @classmethod
    def _next_sequence(cls) -> int:
        _sequence_counters[cls] = _sequence_counters.get(cls, -1) + 1
        return _sequence_counters[cls]

    @classmethod
    def reset_sequence(cls, value: int = 0) -> None:
        """Reset this factory's ``Sequence`` counter to *value* (default 0).

        The next build will use *value* as the first sequence number.  Also
        resets all ``Iterator`` descriptors declared anywhere in the factory's
        MRO so they restart from their first element.

        Typical use — call once per test or in a test fixture::

            def setup_method(self):
                MyFactory.reset_sequence()
        """
        _sequence_counters[cls] = value - 1
        for klass in cls.__mro__:
            if klass in (Factory, object):
                continue
            for field_val in vars(klass).values():
                if isinstance(field_val, Iterator):
                    field_val.reset()

    @classmethod
    def seed(cls, seed_value: int) -> None:
        """Seed all faker-based randomness for deterministic output.

        Seeds the shared module-level ``faker`` instance and any
        locale-specific ``Faker(...)`` descriptor instances declared on this
        factory's MRO.  Call once before a test (or test session) to make
        faker-generated values reproducible::

            def setup_method(self):
                UserFactory.seed(42)
        """
        faker.seed_instance(seed_value)
        for klass in cls.__mro__:
            if klass in (Factory, object):
                continue
            for field_val in vars(klass).values():
                if isinstance(field_val, Faker) and field_val._localized is not None:
                    field_val._localized.seed_instance(seed_value)

    @classmethod
    def _get_traits(cls) -> dict[str, type[Trait]]:
        """Collect all Trait inner classes declared in this factory's MRO."""
        traits: dict[str, type[Trait]] = {}
        for klass in reversed(cls.__mro__):
            if klass in (Factory, object):
                continue
            for name, value in vars(klass).items():
                if (
                    not name.startswith("_")
                    and inspect.isclass(value)
                    and issubclass(value, Trait)
                    and value is not Trait
                ):
                    traits[name] = value
        return traits

    @classmethod
    def _resolve_traits(
        cls, overrides: dict[str, Any]
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """Separate trait bool-kwargs from regular overrides.

        Returns *(trait_fields, remaining_overrides)*.  Trait kwargs (whether
        ``True`` or ``False``) are consumed and never forwarded to the model.
        Later traits in call order win on field conflicts between traits.
        """
        available = cls._get_traits()
        trait_fields: dict[str, Any] = {}
        remaining: dict[str, Any] = {}
        for name, value in overrides.items():
            if name in available:
                if value is True:
                    trait_fields.update(_collect_trait_fields(available[name]))
            else:
                remaining[name] = value
        return trait_fields, remaining

    @classmethod
    def _get_post_generation_hooks(cls) -> list[post_generation]:
        """Collect post_generation hooks in MRO order (base → subclass)."""
        seen: dict[str, post_generation] = {}
        for klass in reversed(cls.__mro__):
            if klass in (Factory, object):
                continue
            for name, value in vars(klass).items():
                if isinstance(value, post_generation):
                    seen[name] = value
        return list(seen.values())

    @classmethod
    def _get_related_factories(
        cls,
    ) -> list[tuple[str, RelatedFactory | RelatedFactoryList]]:
        """Collect RelatedFactory / RelatedFactoryList descriptors in MRO order."""
        seen: dict[str, RelatedFactory | RelatedFactoryList] = {}
        for klass in reversed(cls.__mro__):
            if klass in (Factory, object):
                continue
            for name, value in vars(klass).items():
                if isinstance(value, RelatedFactory | RelatedFactoryList):
                    seen[name] = value
        return list(seen.items())

    @classmethod
    def _build_dict(cls, **overrides: Any) -> dict[str, Any]:
        """Resolve all field descriptors and return the raw field dict.

        SubFactory / FK descriptors are skipped (same as ``build()``).
        """
        trait_fields, effective_overrides = cls._resolve_traits(overrides)
        fields = cls._get_declared_fields()
        merged: dict[str, Any] = {
            **fields,
            **{k: v for k, v in trait_fields.items() if k not in effective_overrides},
        }
        built: dict[str, Any] = {}
        _db_only = SubFactory | _FKSubFactory | _UnresolvableFK
        _computed = LazyAttribute | SelfAttribute | Faker | Sequence | Iterator

        for name, descriptor in merged.items():
            if (
                name in effective_overrides
                or isinstance(descriptor, _db_only)
                or descriptor is Skip
            ):
                continue
            if not isinstance(descriptor, _computed):
                built[name] = descriptor

        for name, descriptor in merged.items():
            if (
                name in effective_overrides
                or isinstance(descriptor, _db_only)
                or descriptor is Skip
            ):
                continue
            if isinstance(descriptor, LazyAttribute):
                built[name] = descriptor.func({**built, **effective_overrides})
            elif isinstance(descriptor, SelfAttribute):
                src = {**built, **effective_overrides}
                parts = descriptor.attr_path.split(".")
                val: Any = src.get(parts[0], descriptor.default)
                for part in parts[1:]:
                    if val is descriptor.default:
                        break
                    val = getattr(val, part, descriptor.default)
                built[name] = val
            elif isinstance(descriptor, Faker):
                built[name] = descriptor.generate()

        for name, descriptor in merged.items():
            if (
                name in effective_overrides
                or isinstance(descriptor, _db_only)
                or descriptor is Skip
            ):
                continue
            if isinstance(descriptor, Sequence):
                built[name] = descriptor.func(cls._next_sequence())
            elif isinstance(descriptor, Iterator):
                built[name] = descriptor._next()

        built.update(effective_overrides)
        return built

    @classmethod
    def build(cls, **overrides: Any) -> T:
        """Build an ORM instance without DB interaction. SubFactory / FK fields are skipped."""
        return cast(T, cls.model(**cls._build_dict(**overrides)))

    @classmethod
    def build_dict(cls, **overrides: Any) -> dict[str, Any]:
        """Return a plain dict of field values without instantiating the model.

        Accepts the same arguments as ``build()`` — trait kwargs, overrides, etc.
        Useful for fixtures, assertions, or feeding data to non-ORM code::

            data = UserFactory.build_dict(name="Alice")
            assert data["name"] == "Alice"
        """
        return cls._build_dict(**overrides)

    @classmethod
    def build_batch(cls, count: int, **overrides: Any) -> list[T]:
        return [cls.build(**overrides) for _ in range(count)]

    @classmethod
    async def create(cls, session: AsyncSession, **overrides: Any) -> T:
        """Build and persist an instance. Caller is responsible for committing."""
        from seedling.exceptions import AutoFactoryResolutionError

        trait_fields, effective_overrides = cls._resolve_traits(overrides)
        fields = cls._get_declared_fields()
        merged: dict[str, Any] = {
            **fields,
            **{k: v for k, v in trait_fields.items() if k not in effective_overrides},
        }
        built: dict[str, Any] = {}
        _db_only = SubFactory | _FKSubFactory | _UnresolvableFK
        _computed = LazyAttribute | SelfAttribute | Faker | Sequence | Iterator

        # 1. Literals
        for name, descriptor in merged.items():
            if name in effective_overrides or descriptor is Skip:
                continue
            if not isinstance(descriptor, _computed | _db_only):
                built[name] = descriptor

        # 2. SubFactories and FK sub-factories (async — each inserts a row)
        for name, descriptor in merged.items():
            if name in effective_overrides or descriptor is Skip:
                continue
            if isinstance(descriptor, SubFactory):
                built[name] = await descriptor.factory.create(session)
            elif isinstance(descriptor, _FKSubFactory):
                related = await descriptor.factory.create(session)
                built[name] = _get_pk_value(related)
            elif isinstance(descriptor, _UnresolvableFK):
                raise AutoFactoryResolutionError(
                    descriptor.factory_name,
                    descriptor.col_name,
                    descriptor.target_table,
                )

        # 3. Computed: LazyAttribute, SelfAttribute, Faker
        for name, descriptor in merged.items():
            if (
                name in effective_overrides
                or isinstance(descriptor, _db_only)
                or descriptor is Skip
            ):
                continue
            if isinstance(descriptor, LazyAttribute):
                built[name] = descriptor.func({**built, **effective_overrides})
            elif isinstance(descriptor, SelfAttribute):
                src = {**built, **effective_overrides}
                parts = descriptor.attr_path.split(".")
                val: Any = src.get(parts[0], descriptor.default)
                for part in parts[1:]:
                    if val is descriptor.default:
                        break
                    val = getattr(val, part, descriptor.default)
                built[name] = val
            elif isinstance(descriptor, Faker):
                built[name] = descriptor.generate()

        # 4. Sequence and Iterator
        for name, descriptor in merged.items():
            if (
                name in effective_overrides
                or isinstance(descriptor, _db_only)
                or descriptor is Skip
            ):
                continue
            if isinstance(descriptor, Sequence):
                built[name] = descriptor.func(cls._next_sequence())
            elif isinstance(descriptor, Iterator):
                built[name] = descriptor._next()

        # 5. Effective overrides (explicit kwargs) replace any computed value
        built.update(effective_overrides)

        instance: T = cast(T, cls.model(**built))
        session.add(instance)
        await session.flush()
        await session.refresh(instance)

        for hook in cls._get_post_generation_hooks():
            result = hook.func(instance, session)
            if inspect.iscoroutine(result):
                await result

        for _name, related in cls._get_related_factories():
            await related.generate(instance, session)

        return instance

    @classmethod
    async def create_batch(
        cls,
        session: AsyncSession,
        count: int,
        *,
        bulk: bool = False,
        **overrides: Any,
    ) -> list[T]:
        """Create *count* instances.

        When ``bulk=True``, uses a single ``INSERT ... RETURNING`` statement
        via the SQLAlchemy Core ORM DML API.  This is significantly faster for
        large batches because it skips per-row flush/refresh cycles.

        **Limitations of bulk mode:**

        - ``@post_generation`` hooks do **not** fire.
        - ``RelatedFactory`` / ``RelatedFactoryList`` do **not** fire.
        - ``SubFactory`` and FK-auto-resolve fields are omitted from the insert
          dict (the caller must supply those values via overrides).
        """
        if not bulk:
            return [await cls.create(session, **overrides) for _ in range(count)]

        dicts = [cls._build_dict(**overrides) for _ in range(count)]
        if not dicts:
            return []
        from sqlalchemy.engine import ScalarResult

        scalars: ScalarResult[T] = await session.scalars(
            sa_insert(cls.model).returning(cls.model), dicts
        )
        return list(scalars.all())


def get_factory(model: type) -> type[Factory[Any]] | None:
    """Return the registered factory for *model*, or None if none is registered."""
    return _registry.get(model)


def _clear_registry() -> None:
    _registry.clear()


def _get_pk_value(instance: Any) -> Any:
    """Return the single-column primary key value from a mapped instance."""
    mapper = sa_inspect(type(instance))
    for col_attr in mapper.mapper.column_attrs:
        if any(col.primary_key for col in col_attr.columns):
            return getattr(instance, col_attr.key)
    raise ValueError(
        f"AutoFactory: cannot extract PK from {type(instance).__name__} — no PK column found."
    )


def _smart_heuristic(col_name: str) -> LazyAttribute | None:
    """Return a LazyAttribute for name-based smart defaults, or None."""
    fn: Callable[[], Any] | None = _NAME_HEURISTICS.get(col_name.lower())
    if fn is None:
        return None
    captured: Callable[[], Any] = fn
    return LazyAttribute(lambda _: captured())


def _default_for_col_type(col: Any) -> Any:
    """Return a descriptor default for a column's SQLAlchemy type, or None to skip."""
    t = col.type
    if isinstance(t, (sa_types.String, sa_types.Text)):
        return Sequence(lambda n: f"value-{n}")
    if isinstance(t, (sa_types.Integer, sa_types.BigInteger, sa_types.SmallInteger)):
        return Sequence(lambda n: n)
    if isinstance(t, sa_types.Float):
        return LazyAttribute(lambda _: 0.0)
    if isinstance(t, sa_types.Numeric):
        return LazyAttribute(lambda _: 0)
    if isinstance(t, sa_types.Boolean):
        return False
    if isinstance(t, sa_types.Date):
        return LazyAttribute(lambda _: _dt.date.today())
    if isinstance(t, sa_types.DateTime):
        return LazyAttribute(lambda _: _dt.datetime.now())
    if isinstance(t, sa_types.Uuid):
        return LazyAttribute(lambda _: _uuid.uuid4())
    return None


class AutoFactory(Factory[T]):
    """Factory that auto-generates field defaults via SQLAlchemy mapper introspection.

    Subclass this instead of Factory when you want sensible defaults without
    declaring every field. Explicitly declared fields always override auto-generated ones.

    Set ``class Meta: smart_defaults = False`` to disable name-based heuristics.
    """

    class Meta:
        smart_defaults = True

    @classmethod
    def _smart_defaults_on(cls) -> bool:
        for klass in cls.__mro__:
            if klass is AutoFactory:
                break
            if "Meta" in vars(klass):
                return bool(getattr(vars(klass)["Meta"], "smart_defaults", True))
        return True

    @classmethod
    def _resolve_fk(cls, col_name: str, col: Any) -> Any:
        """Return _FKSubFactory, _UnresolvableFK, or None (nullable + no factory = skip)."""
        fk = next(iter(col.foreign_keys))
        target_table = fk.column.table

        model = vars(cls).get("model") or getattr(cls, "model", None)
        factory_name = cls.__name__

        if model is not None:
            try:
                mapper = sa_inspect(model)
                for other_mapper in mapper.mapper.registry.mappers:
                    if other_mapper.persist_selectable is target_table or (
                        other_mapper.persist_selectable.name == target_table.name
                    ):
                        target_model = other_mapper.class_
                        registered = get_factory(target_model)
                        if registered is not None:
                            return _FKSubFactory(registered)
                        if col.nullable:
                            return None
                        return _UnresolvableFK(
                            col_name, target_table.name, factory_name
                        )
            except Exception:
                pass

        if col.nullable:
            return None
        return _UnresolvableFK(col_name, target_table.name, factory_name)

    @classmethod
    def _introspect_model(cls) -> dict[str, Any]:
        model = vars(cls).get("model") or getattr(cls, "model", None)
        if model is None:
            return {}

        try:
            mapper = sa_inspect(model)
        except Exception:
            return {}

        smart = cls._smart_defaults_on()
        fields: dict[str, Any] = {}

        for col_attr in mapper.mapper.column_attrs:
            col = col_attr.columns[0]
            name = col_attr.key

            if col.primary_key:
                continue

            if col.foreign_keys:
                resolved = cls._resolve_fk(name, col)
                if resolved is not None:
                    fields[name] = resolved
                continue

            if smart:
                heuristic = _smart_heuristic(name)
                if heuristic is not None:
                    fields[name] = heuristic
                    continue

            default = _default_for_col_type(col)
            if default is not None:
                fields[name] = default

        return fields

    @classmethod
    def _get_declared_fields(cls) -> dict[str, Any]:
        auto = cls._introspect_model()
        declared = super()._get_declared_fields()
        return {**auto, **declared}
