"""Explicit descriptors for compatibility facades over repositories."""

from __future__ import annotations

from typing import Any


class RepositoryMethod:
    """Expose one same-named repository method on a compatibility facade."""

    __slots__ = ("repository_attribute", "method_name")

    def __init__(self, repository_attribute: str):
        self.repository_attribute = repository_attribute
        self.method_name = ""

    def __set_name__(self, owner: type[object], name: str) -> None:
        self.method_name = name

    def __get__(self, instance: object | None, owner: type[object] | None = None) -> Any:
        if instance is None:
            return self
        repository = getattr(instance, self.repository_attribute)
        return getattr(repository, self.method_name)
