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


class AutoFactoryResolutionError(ValueError):
    def __init__(self, factory_name: str, col_name: str, target_table: str) -> None:
        super().__init__(
            f"AutoFactory[{factory_name}]: FK column '{col_name}' → table '{target_table}' "
            f"has no registered factory. "
            f"Pass {col_name}=... as an override or register a factory for the target model."
        )
