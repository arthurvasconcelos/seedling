from __future__ import annotations

from collections import deque

from seedling.exceptions import CircularDependencyError, MissingDependencyError
from seedling.seeder import Seeder


def topological_sort(seeders: list[type[Seeder]]) -> list[type[Seeder]]:
    in_degree: dict[type[Seeder], int] = dict.fromkeys(seeders, 0)
    dependents: dict[type[Seeder], list[type[Seeder]]] = {s: [] for s in seeders}

    for seeder in seeders:
        for dep in seeder.depends_on:
            if dep not in in_degree:
                raise MissingDependencyError(seeder, dep)
            in_degree[seeder] += 1
            dependents[dep].append(seeder)

    queue = deque(s for s, deg in in_degree.items() if deg == 0)
    result: list[type[Seeder]] = []

    while queue:
        node = queue.popleft()
        result.append(node)
        for dependent in dependents[node]:
            in_degree[dependent] -= 1
            if in_degree[dependent] == 0:
                queue.append(dependent)

    if len(result) != len(seeders):
        cycle = [s.__name__ for s in seeders if s not in result]
        raise CircularDependencyError(cycle)

    return result


def resolve_with_deps(
    requested: list[type[Seeder]],
    registry: list[type[Seeder]],
) -> list[type[Seeder]]:
    """Walk depends_on recursively to collect all required seeders."""
    needed: set[type[Seeder]] = set()

    def walk(cls: type[Seeder]) -> None:
        if cls in needed:
            return
        needed.add(cls)
        for dep in cls.depends_on:
            walk(dep)

    for cls in requested:
        walk(cls)

    all_ordered = topological_sort(registry)
    return [s for s in all_ordered if s in needed]
