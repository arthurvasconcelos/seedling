# Factories

`Factory[T]` generates ORM model instances with realistic data for use in seeders and
tests.  Phase 0.4 added `AutoFactory`, declarative `Trait` classes, `@post_generation`
hooks, `RelatedFactory`, and a full set of field descriptors.

---

## Defining a factory

Subclass `Factory[T]` and set `model` to the SQLAlchemy mapped class.  Field
declarations at class level become the default values for each instance.

```python
from seedling import Factory, Faker, LazyAttribute, Sequence, SubFactory
from myapp.models import User, Post

class UserFactory(Factory[User]):
    model = User
    name  = Faker("name")
    email = Faker("email")

class PostFactory(Factory[Post]):
    model = Post
    title  = Faker("sentence")
    author = SubFactory(UserFactory)
```

### AutoFactory

`AutoFactory[T]` introspects the SQLAlchemy mapper and generates sensible defaults
automatically — no field declarations required.

```python
from seedling import AutoFactory
from myapp.models import User

class UserFactory(AutoFactory[User]):
    model = User
```

Auto-generated defaults by column type:

| SQLAlchemy type | Default |
|-----------------|---------|
| `String` / `Text` | `"value-N"` (unique per build) |
| `Integer` / `BigInteger` / `SmallInteger` | `N` (unique per build) |
| `Boolean` | `False` |
| `Date` | `date.today()` |
| `DateTime` | `datetime.now()` |
| `Uuid` | `uuid4()` |
| `Float` / `Numeric` | `0` |

Primary keys are always skipped.

#### Smart defaults

When `class Meta: smart_defaults = True` (the default), named columns get faker-based
values automatically:

| Column name | Default |
|-------------|---------|
| `email` | `faker.email()` |
| `first_name` | `faker.first_name()` |
| `last_name` | `faker.last_name()` |
| `name` | `faker.name()` |
| `phone` / `phone_number` | `faker.phone_number()` |
| `username` | `faker.user_name()` |
| `address` | `faker.address()` |
| `city` | `faker.city()` |
| `country` | `faker.country()` |
| `url` / `website` | `faker.url()` |
| `description` | `faker.sentence()` |
| `title` | `faker.sentence(nb_words=4)` |
| `slug` | `faker.slug()` |
| `company` / `company_name` | `faker.company()` |

Opt out per factory:

```python
class UserFactory(AutoFactory[User]):
    model = User

    class Meta:
        smart_defaults = False
```

#### FK resolution

FK columns are resolved by looking up the target model's factory in the factory
registry.  If found, a related row is created automatically.  If not found:

- **Nullable FK** — field is left unset (DB default / `None`).
- **Non-nullable FK** — `AutoFactoryResolutionError` is raised at `create()` time.

Pass the FK value explicitly to bypass auto-resolution entirely:

```python
article = await ArticleFactory.create(session, author_id=42)
```

#### Overriding auto-generated fields

Explicitly declared fields always win over auto-generated ones:

```python
class UserFactory(AutoFactory[User]):
    model = User
    email = "fixed@example.com"          # overrides smart default
    bio   = Skip                          # suppresses the auto-generated default
```

---

## Field descriptors

### `Faker(provider, *args, locale=None, **kwargs)`

Calls a `faker` provider by name each build:

```python
email   = Faker("email")
name    = Faker("name", locale="fr_FR")
code    = Faker("numerify", text="###-##")
```

### `LazyAttribute(func)`

Evaluated once per build, receiving the partially-built field dict:

```python
handle = LazyAttribute(lambda f: f["email"].split("@")[0])
```

### `SelfAttribute(attr_path, default=None)`

References a sibling field by name.  Dot-notation traverses attributes:

```python
username = SelfAttribute("email")
city     = SelfAttribute("address.city", default="Unknown")
```

### `Sequence(func)`

Auto-incrementing counter shared across all builds of the factory:

```python
code = Sequence(lambda n: f"ID-{n:04d}")   # ID-0000, ID-0001, ...
```

### `Iterator(values)`

Cycles through a fixed list, wrapping around:

```python
role = Iterator(["admin", "user", "moderator"])
```

### `SubFactory(OtherFactory)`

Creates a related instance by calling `OtherFactory.create()` (in `create()`) or
skips the field in `build()`:

```python
author = SubFactory(UserFactory)
```

### `Skip`

Omits a field entirely — the model's `__init__` never receives it:

```python
class UserFactory(AutoFactory[User]):
    model = User
    internal_flag = Skip   # suppress the auto-generated default
```

---

## Traits

Declare traits as inner classes that subclass `Trait`.  Apply them via bool kwargs.

```python
from seedling import Factory, Trait

class UserFactory(Factory[User]):
    model     = User
    name      = Faker("name")
    email     = Faker("email")
    is_active = True
    is_staff  = False

    class inactive(Trait):
        is_active = False

    class admin(Trait):
        is_staff  = True
        is_active = True
```

```python
user = UserFactory.build(inactive=True)
user = UserFactory.build(admin=True)
user = UserFactory.build(admin=True, inactive=True)   # stackable — later wins
user = UserFactory.build(admin=True, is_staff=False)  # explicit kwarg beats trait
```

Traits support all descriptors — `LazyAttribute`, `Sequence`, `Faker`, etc.

Traits are inherited through the factory MRO.  A child factory can override a parent
trait by declaring a trait with the same name.

`trait_name=False` suppresses the trait and is consumed (not forwarded to the model).

---

## Post-generation hooks

`@post_generation` decorates an async (or sync) method that fires after the instance
has been flushed and refreshed in `create()`.  Silently skipped in `build()`.

```python
from seedling import post_generation

class UserFactory(Factory[User]):
    model = User
    email = Faker("email")

    @post_generation
    async def assign_role(instance, session):
        role = await RoleFactory.create(session, user_id=instance.id)
```

- The function receives `(instance, session)`.
- Multiple hooks on one factory fire in MRO order (base → subclass, declaration order).
- A child factory can override a parent hook by using the same method name.

---

## Related factories

Create related rows automatically after the main instance is persisted.

### `RelatedFactory(factory, **kwargs)`

Creates one related instance.  Callable kwargs receive the parent instance:

```python
from seedling import RelatedFactory

class AuthorFactory(Factory[Author]):
    model = Author
    email = Faker("email")

    # Creates one Article pointing back to this Author
    default_article = RelatedFactory(
        ArticleFactory,
        author_id=lambda inst: inst.id,
        title="Introduction",
    )
```

### `RelatedFactoryList(factory, size=1, **kwargs)`

Creates `size` related instances:

```python
articles = RelatedFactoryList(ArticleFactory, size=5, author_id=lambda i: i.id)
```

`RelatedFactory` / `RelatedFactoryList` fire after `@post_generation` hooks.
Both are silently skipped in `build()`.

---

## Building instances

```python
# In-memory, no DB
user  = UserFactory.build()
user  = UserFactory.build(name="Alice", admin=True)
users = UserFactory.build_batch(5)

# Dict (no ORM instance)
data  = UserFactory.build_dict()
data  = UserFactory.build_dict(name="Alice")
```

`build()` and `build_dict()` skip all DB-only descriptors (`SubFactory`,
`RelatedFactory`, FK auto-resolve) and all `@post_generation` hooks.

---

## Persisting instances

```python
# Single row
user = await UserFactory.create(session)
user = await UserFactory.create(session, name="Bob", admin=True)

# Multiple rows (per-row, with hooks)
users = await UserFactory.create_batch(session, 10)

# Bulk insert — fast, no hooks
users = await UserFactory.create_batch(session, 1000, bulk=True)
```

**`bulk=True` limitations:** `@post_generation` hooks and `RelatedFactory` /
`RelatedFactoryList` do **not** fire.  `SubFactory` and FK-auto-resolve fields are
omitted — supply them via overrides.

---

## Factory registry

Every factory that declares `model = ...` on its own body is automatically registered.
Look up a factory by model class:

```python
from seedling import get_factory

factory_cls = get_factory(User)   # UserFactory, or None
```

`AutoFactory` uses the registry internally for FK resolution.

---

## Test utilities

### `reset_sequence(value=0)`

Resets the `Sequence` counter and all `Iterator` fields in the factory's MRO:

```python
def setup_method(self):
    UserFactory.reset_sequence()
    UserFactory.reset_sequence(100)   # start at 100
```

### `seed(n)`

Seeds the `faker` instance for deterministic output:

```python
def setup_method(self):
    UserFactory.seed(42)
```

---

## Migration guide: `as_trait()` → `Trait`

`as_trait()` has been removed in 0.4.  Replace functional call-site trait creation with
declarative inner `Trait` classes.

**Before (0.3):**

```python
class UserFactory(Factory[User]):
    model     = User
    is_active = True
    is_staff  = False

inactive = UserFactory.as_trait(is_active=False)
admin    = UserFactory.as_trait(is_staff=True)

# Usage
inactive.build()
admin.create(session)
```

**After (0.4):**

```python
class UserFactory(Factory[User]):
    model     = User
    is_active = True
    is_staff  = False

    class inactive(Trait):
        is_active = False

    class admin(Trait):
        is_staff = True

# Usage
UserFactory.build(inactive=True)
await UserFactory.create(session, admin=True)
```

Key differences:

- Traits are **stackable** — pass multiple booleans to combine them.
- `trait_name=False` suppresses a trait without forwarding the kwarg to the model.
- Traits inherit through the factory MRO — define once, reuse in subclasses.
- `LazyAttribute`, `Sequence`, `Faker`, and other descriptors work inside `Trait` bodies.
