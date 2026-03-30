from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from seedling.exceptions import CircularDependencyError, MissingDependencyError
from seedling.resolver import resolve_with_deps, topological_sort
from seedling.seeder import Seeder


class SeedA(Seeder):
    async def run(self, session: AsyncSession) -> None:
        pass


class SeedB(Seeder):
    depends_on = [SeedA]

    async def run(self, session: AsyncSession) -> None:
        pass


class SeedC(Seeder):
    depends_on = [SeedB]

    async def run(self, session: AsyncSession) -> None:
        pass


class SeedD(Seeder):
    depends_on = [SeedA]

    async def run(self, session: AsyncSession) -> None:
        pass


def test_topological_sort_no_deps():
    result = topological_sort([SeedA])
    assert result == [SeedA]


def test_topological_sort_linear_chain():
    result = topological_sort([SeedA, SeedB, SeedC])
    assert result.index(SeedA) < result.index(SeedB)
    assert result.index(SeedB) < result.index(SeedC)


def test_topological_sort_diamond():
    result = topological_sort([SeedA, SeedB, SeedD])
    assert result.index(SeedA) < result.index(SeedB)
    assert result.index(SeedA) < result.index(SeedD)


def test_topological_sort_order_independent():
    result1 = topological_sort([SeedA, SeedB, SeedC])
    result2 = topological_sort([SeedC, SeedB, SeedA])
    # Both must produce a valid ordering (A before B before C)
    assert result1.index(SeedA) < result1.index(SeedB) < result1.index(SeedC)
    assert result2.index(SeedA) < result2.index(SeedB) < result2.index(SeedC)


def test_topological_sort_missing_dependency_raises():
    class Orphan(Seeder):
        depends_on = [SeedA]

        async def run(self, session: AsyncSession) -> None:
            pass

    with pytest.raises(MissingDependencyError):
        topological_sort([Orphan])  # SeedA not in the list


def test_topological_sort_circular_raises():
    class X(Seeder):
        async def run(self, session: AsyncSession) -> None:
            pass

    class Y(Seeder):
        async def run(self, session: AsyncSession) -> None:
            pass

    X.depends_on = [Y]  # type: ignore[assignment]
    Y.depends_on = [X]  # type: ignore[assignment]

    with pytest.raises(CircularDependencyError):
        topological_sort([X, Y])

    # Clean up to avoid polluting other tests
    X.depends_on = []  # type: ignore[assignment]
    Y.depends_on = []  # type: ignore[assignment]


def test_resolve_with_deps_pulls_in_dependencies():
    registry = [SeedA, SeedB, SeedC]
    result = resolve_with_deps([SeedC], registry)
    assert SeedA in result
    assert SeedB in result
    assert SeedC in result
    assert result.index(SeedA) < result.index(SeedB) < result.index(SeedC)


def test_resolve_with_deps_excludes_unrequested():
    registry = [SeedA, SeedB, SeedC, SeedD]
    result = resolve_with_deps([SeedB], registry)
    assert SeedA in result
    assert SeedB in result
    assert SeedD not in result
    assert SeedC not in result


def test_resolve_with_deps_no_deps():
    registry = [SeedA, SeedB]
    result = resolve_with_deps([SeedA], registry)
    assert result == [SeedA]


def test_missing_dependency_error_message():
    class Missing(Seeder):
        async def run(self, session: AsyncSession) -> None:
            pass

    err = MissingDependencyError(SeedB, Missing)
    assert "SeedB" in str(err)
    assert "Missing" in str(err)
