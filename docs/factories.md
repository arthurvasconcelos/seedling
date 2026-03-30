# Factories

`Factory[T]` generates ORM model instances with realistic data for use in seeders and tests.

## Defining a factory

```python
from seedling import Factory, LazyAttribute, Sequence, SubFactory, faker
from myapp.models import User, Post

class UserFactory(Factory[User]):
    model = User

    id = Sequence(lambda n: n)
    email = LazyAttribute(lambda o: f"user{o.id}@example.com")
    name = LazyAttribute(lambda _: faker.name())
    is_active = True

class PostFactory(Factory[Post]):
    model = Post

    id = Sequence(lambda n: n)
    title = LazyAttribute(lambda _: faker.sentence())
    author = SubFactory(UserFactory)
```

## Building instances

`build()` creates an in-memory instance without touching the database:

```python
user = UserFactory.build()
user = UserFactory.build(name="Alice", email="alice@example.com")

users = UserFactory.build_batch(5)
```

## Persisting instances

`create()` adds the instance to the session and commits:

```python
async def run(self, session: AsyncSession) -> None:
    await UserFactory.create(session)
    await UserFactory.create(session, name="Bob")
    await UserFactory.create_batch(session, 10)
```

## Traits

Use `as_trait()` to define named variations:

```python
class UserFactory(Factory[User]):
    model = User
    name = LazyAttribute(lambda _: faker.name())
    is_active = True

    inactive = as_trait(is_active=False)
    admin = as_trait(role="admin", is_active=True)
```

Apply a trait by passing it as a keyword argument:

```python
user = UserFactory.build(inactive=True)
```

## LazyAttribute

`LazyAttribute` receives the partially-built object so it can reference other fields:

```python
email = LazyAttribute(lambda o: f"{o.name.lower()}@example.com")
```

## Sequence

`Sequence` increments a counter per factory class across the process lifetime:

```python
id = Sequence(lambda n: n)          # 0, 1, 2, ...
code = Sequence(lambda n: f"ID-{n}") # ID-0, ID-1, ...
```

## SubFactory

`SubFactory` builds a related object using another factory:

```python
author = SubFactory(UserFactory)
```

Override sub-factory fields by passing a dict:

```python
post = PostFactory.build(author={"name": "Alice"})
```
