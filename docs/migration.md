# Migrate from factory_boy

This guide shows side-by-side comparisons for the most common factory_boy patterns
and their seedling equivalents. factory_boy and seedling share several concepts
(`LazyAttribute`, `Sequence`, `SubFactory`, `RelatedFactory`) but differ in two
important ways:

1. **seedling is async-first** — `create()` and `create_batch()` are coroutines.
2. **seedling passes a session** — no global session state; the caller decides which
   session to use.

---

## Defining a factory

**factory_boy**

```python
import factory
from myapp.models import User

class UserFactory(factory.Factory):
    class Meta:
        model = User

    email = factory.Faker("email")
    name  = factory.Faker("name")
```

**seedling**

```python
from seedling import Factory, Faker
from myapp.models import User

class UserFactory(Factory[User]):
    model = User
    email = Faker("email")
    name  = Faker("name")
```

The `model` class attribute replaces `class Meta: model = ...`.

---

## Building instances

**factory_boy**

```python
user  = UserFactory.build()
users = UserFactory.build_batch(5)
data  = UserFactory.stub()            # dict-like object
```

**seedling**

```python
user  = UserFactory.build()
users = UserFactory.build_batch(5)
data  = UserFactory.build_dict()      # plain dict
```

`build()` and `build_batch()` are synchronous in both libraries.

---

## Persisting instances

**factory_boy** (with factory_boy-sqlalchemy)

```python
from factory.alchemy import SQLAlchemyModelFactory

class UserFactory(SQLAlchemyModelFactory):
    class Meta:
        model = User
        sqlalchemy_session = db_session

    email = factory.Faker("email")

user  = UserFactory.create()
users = UserFactory.create_batch(5)
```

**seedling**

```python
from seedling import Factory, Faker

class UserFactory(Factory[User]):
    model = User
    email = Faker("email")

user  = await UserFactory.create(session)
users = await UserFactory.create_batch(session, 5)
```

seedling always takes an explicit `session` argument — there is no global session to
configure.

---

## LazyAttribute

**factory_boy**

```python
class UserFactory(factory.Factory):
    class Meta:
        model = User

    email    = factory.Faker("email")
    username = factory.LazyAttribute(lambda o: o.email.split("@")[0])
```

**seedling**

```python
class UserFactory(Factory[User]):
    model    = User
    email    = Faker("email")
    username = LazyAttribute(lambda f: f["email"].split("@")[0])
```

seedling's `LazyAttribute` receives the partially-built field **dict** (`f`), not
an object with attribute access. Use `f["field_name"]` to reference sibling fields.

---

## Sequence

```python
# factory_boy
code = factory.Sequence(lambda n: f"item-{n}")

# seedling (identical API)
from seedling import Sequence
code = Sequence(lambda n: f"item-{n}")
```

---

## SubFactory

```python
# factory_boy
class PostFactory(factory.Factory):
    class Meta:
        model = Post
    author = factory.SubFactory(UserFactory)

# seedling (identical API)
from seedling import SubFactory
class PostFactory(Factory[Post]):
    model  = Post
    author = SubFactory(UserFactory)
```

In seedling, `SubFactory` calls `UserFactory.create(session)` when the outer
factory runs `create()`, and is skipped in `build()`.

---

## Traits

**factory_boy**

```python
class UserFactory(factory.Factory):
    class Meta:
        model = User

    class Params:
        admin = factory.Trait(
            is_staff=True,
        )

user = UserFactory(admin=True)
```

**seedling**

```python
from seedling import Factory, Trait

class UserFactory(Factory[User]):
    model    = User
    is_staff = False

    class admin(Trait):
        is_staff = True

user = UserFactory.build(admin=True)
```

seedling `Trait` classes are **stackable**: pass multiple booleans to combine
them. `trait_name=False` suppresses a trait without forwarding the kwarg to the model.

---

## `@post_generation`

**factory_boy**

```python
class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = User

    @factory.post_generation
    def groups(self, create, extracted, **kwargs):
        if not create or not extracted:
            return
        for group in extracted:
            self.groups.add(group)
```

**seedling**

```python
from seedling import Factory, post_generation

class UserFactory(Factory[User]):
    model = User

    @post_generation
    async def assign_default_role(instance, session):
        await RoleFactory.create(session, user_id=instance.id)
```

Key differences:
- seedling hooks are `async` by default (sync functions are also accepted).
- The hook receives `(instance, session)`, not `(self, create, extracted)`.
- There is no `extracted` parameter — use `SubFactory` or `RelatedFactory` instead.
- Hooks fire after the instance is flushed and refreshed in the DB.

---

## RelatedFactory

**factory_boy**

```python
class AuthorFactory(factory.Factory):
    class Meta:
        model = Author

    default_book = factory.RelatedFactory(
        BookFactory,
        factory_related_name="author",
    )
```

**seedling**

```python
from seedling import RelatedFactory

class AuthorFactory(Factory[Author]):
    model = Author
    default_book = RelatedFactory(
        BookFactory,
        author_id=lambda inst: inst.id,
    )
```

In seedling, callable kwargs receive the parent instance; non-callable kwargs are
forwarded as-is.

---

## Bulk insert

**factory_boy** has no built-in bulk insert path.

**seedling**

```python
# Per-row (hooks fire, SubFactory resolved)
users = await UserFactory.create_batch(session, 1_000)

# Bulk — uses INSERT ... RETURNING, much faster for large batches
users = await UserFactory.create_batch(session, 100_000, bulk=True)
```

`bulk=True` limitations: `@post_generation` hooks and `RelatedFactory` /
`RelatedFactoryList` do not fire. `SubFactory` and FK auto-resolve fields are
omitted — supply them via overrides.

---

## AutoFactory — no factory_boy equivalent

seedling's `AutoFactory[T]` introspects the SQLAlchemy mapper and generates
sensible defaults automatically:

```python
from seedling import AutoFactory

class UserFactory(AutoFactory[User]):
    model = User
    # email → faker.email(), name → faker.name(), etc. (smart defaults on by default)
```

There is no equivalent in factory_boy. It removes the need to declare every field
explicitly for simple models.

---

## Faker descriptor

**factory_boy**

```python
email = factory.Faker("email")
code  = factory.Faker("numerify", text="###-##")
name  = factory.Faker("name", locale="fr_FR")
```

**seedling**

```python
from seedling import Faker
email = Faker("email")
code  = Faker("numerify", text="###-##")
name  = Faker("name", locale="fr_FR")
```

Identical semantics; different import path.

---

## Deterministic output

**factory_boy**

```python
factory.random.reseed_random(42)
```

**seedling**

```python
UserFactory.seed(42)   # seeds faker and all Iterator descriptors
```

---

## What seedling adds beyond factory_boy

| Feature | factory_boy | seedling |
|---------|-------------|---------|
| Async create/create_batch | ✗ | ✓ |
| Explicit session argument | ✗ (global) | ✓ |
| AutoFactory (mapper introspection) | ✗ | ✓ |
| Bulk insert path | ✗ | ✓ (`bulk=True`) |
| State tracking + audit log | ✗ | ✓ |
| Seeder dependency runner | ✗ | ✓ |
| CLI (`seed run`, `seed fresh`, etc.) | ✗ | ✓ |
| `SelfAttribute`, `Iterator`, `Skip` | ✗ | ✓ |
