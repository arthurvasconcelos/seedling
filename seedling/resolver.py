from __future__ import annotations

from seedling.exceptions import CircularDependencyError, MissingDependencyError
from seedling.seeder import Seeder


def topological_levels(seeders: list[type[Seeder]]) -> list[list[type[Seeder]]]:
    """Group seeders by dependency level.

    Seeders within the same level have no dependencies on each other and can
    run in parallel. Levels must be executed in order.
    """
    in_degree: dict[type[Seeder], int] = dict.fromkeys(seeders, 0)
    dependents: dict[type[Seeder], list[type[Seeder]]] = {s: [] for s in seeders}

    for seeder in seeders:
        for dep in seeder.depends_on:
            if dep not in in_degree:
                raise MissingDependencyError(seeder, dep)
            in_degree[seeder] += 1
            dependents[dep].append(seeder)

    frontier = [s for s, deg in in_degree.items() if deg == 0]
    levels: list[list[type[Seeder]]] = []

    while frontier:
        levels.append(frontier)
        next_frontier: list[type[Seeder]] = []
        for node in frontier:
            for dependent in dependents[node]:
                in_degree[dependent] -= 1
                if in_degree[dependent] == 0:
                    next_frontier.append(dependent)
        frontier = next_frontier

    total = sum(len(level) for level in levels)
    if total != len(seeders):
        seen = {s for level in levels for s in level}
        cycle = [s.__name__ for s in seeders if s not in seen]
        raise CircularDependencyError(cycle)

    return levels


def topological_sort(seeders: list[type[Seeder]]) -> list[type[Seeder]]:
    return [s for level in topological_levels(seeders) for s in level]


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
