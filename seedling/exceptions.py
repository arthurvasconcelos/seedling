from __future__ import annotations


class CircularDependencyError(Exception):
    def __init__(self, cycle: list[str]) -> None:
        names = " \u2192 ".join(cycle + [cycle[0]])
        super().__init__(f"Circular dependency detected: {names}")


class MissingDependencyError(Exception):
    def __init__(self, seeder: type, missing: type) -> None:
        super().__init__(
            f"{seeder.__name__} declares dependency on {missing.__name__}, "
            "but it is not registered."
        )
