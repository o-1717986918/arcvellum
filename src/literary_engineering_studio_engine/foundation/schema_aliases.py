"""Central schema identity aliases for project migration and legacy reads."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SchemaAlias:
    canonical: str
    aliases: frozenset[str]
    migratable: bool = True

    def accepts(self, value: object) -> bool:
        identity = str(value or "").strip()
        return identity == self.canonical or identity in self.aliases


class SchemaAliasRegistry:
    """Resolve bounded historical identities without weakening schema checks."""

    def __init__(self, entries: tuple[SchemaAlias, ...] = ()) -> None:
        self._by_identity: dict[str, SchemaAlias] = {}
        for entry in entries:
            self.register(entry)

    def register(self, entry: SchemaAlias) -> None:
        identities = (entry.canonical, *entry.aliases)
        conflicts = [value for value in identities if value in self._by_identity]
        if conflicts:
            raise ValueError(f"schema alias already registered: {', '.join(conflicts)}")
        for value in identities:
            if not value or value.strip() != value:
                raise ValueError("schema identities must be non-empty and normalized")
            self._by_identity[value] = entry

    def resolve(self, value: object) -> str:
        identity = str(value or "").strip()
        entry = self._by_identity.get(identity)
        return entry.canonical if entry is not None else identity

    def matches(self, value: object, expected: object) -> bool:
        actual = str(value or "").strip()
        target = str(expected or "").strip()
        if not actual or not target:
            return actual == target
        return self.resolve(actual) == self.resolve(target)

    def migration_target(self, value: object) -> str | None:
        identity = str(value or "").strip()
        entry = self._by_identity.get(identity)
        if entry is None or not entry.migratable or identity == entry.canonical:
            return None
        return entry.canonical

    def entries(self) -> tuple[SchemaAlias, ...]:
        return tuple(
            sorted(
                {entry.canonical: entry for entry in self._by_identity.values()}.values(),
                key=lambda item: item.canonical,
            )
        )


PROJECT_SCHEMA = "arcvellum/project/v2"
PROJECT_READING_SCHEMA = "arcvellum/project-reading/v2"
COMPLETION_SCHEMA = "arcvellum/agent-task-completion/v1"
STYLE_EVAL_SCHEMA = "arcvellum/style-eval/v1"
STYLE_SKILL_SCHEMA = "arcvellum/style-skill/v1"


SCHEMA_ALIASES = SchemaAliasRegistry(
    (
        SchemaAlias(PROJECT_SCHEMA, frozenset({"literary-engineering-workbench/project/v1"})),
        SchemaAlias(PROJECT_READING_SCHEMA, frozenset({"literary-work-project/v0.1"})),
        SchemaAlias(
            COMPLETION_SCHEMA,
            frozenset({"literary-engineering-workbench/agent-task-completion/v1"}),
        ),
        SchemaAlias(
            STYLE_EVAL_SCHEMA,
            frozenset({"literary-engineering-workbench/style-eval/v0.1"}),
        ),
        SchemaAlias(
            STYLE_SKILL_SCHEMA,
            frozenset({"literary-engineering-workbench/style-skill/v0.1"}),
        ),
    )
)


def canonical_schema(value: object) -> str:
    return SCHEMA_ALIASES.resolve(value)


def schema_matches(value: object, expected: object) -> bool:
    return SCHEMA_ALIASES.matches(value, expected)


def canonicalize_schema_fields(value: object, *, key: str = "") -> object:
    """Return a copy with only registered schema-valued fields canonicalized."""

    if isinstance(value, dict):
        return {
            item_key: canonicalize_schema_fields(item, key=str(item_key))
            for item_key, item in value.items()
        }
    if isinstance(value, list):
        return [canonicalize_schema_fields(item, key=key) for item in value]
    if isinstance(value, str) and key in {"schema", "$id", "schema_value"}:
        return canonical_schema(value)
    return value


__all__ = [
    "canonical_schema",
    "canonicalize_schema_fields",
    "COMPLETION_SCHEMA",
    "PROJECT_READING_SCHEMA",
    "PROJECT_SCHEMA",
    "SCHEMA_ALIASES",
    "SchemaAlias",
    "SchemaAliasRegistry",
    "schema_matches",
    "STYLE_EVAL_SCHEMA",
    "STYLE_SKILL_SCHEMA",
]
