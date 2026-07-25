"""Round-trip document codec for controlled Archive asset editing."""

from __future__ import annotations

from dataclasses import dataclass
from io import StringIO
import json
from typing import Any, Mapping

from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap
from ruamel.yaml.constructor import DuplicateKeyError
from ruamel.yaml.error import YAMLError
from ruamel.yaml.scalarstring import ScalarString

from .contracts import AssetViewDefinition


MAX_DOCUMENT_DEPTH = 48
MAX_DOCUMENT_NODES = 20_000


class AssetDocumentError(ValueError):
    """Raised when an editable asset is not a bounded mapping document."""


@dataclass(frozen=True)
class ParsedAssetDocument:
    document_format: str
    mapping: Mapping[str, Any]
    native: Any

    def json_safe_mapping(self) -> dict[str, Any]:
        return _json_safe(self.mapping)


def parse_asset_document(
    definition: AssetViewDefinition,
    content: str,
) -> ParsedAssetDocument:
    document_format = _document_format(definition)
    if document_format == "json":
        native = _parse_json(content)
    else:
        native = _parse_yaml(content)
    if not isinstance(native, Mapping):
        raise AssetDocumentError(
            f"{document_format.upper()} asset root must be an object."
        )
    if any(not isinstance(key, str) for key in native):
        raise AssetDocumentError("Asset root keys must be text.")
    _check_document_bounds(native)
    return ParsedAssetDocument(document_format, native, native)


def render_asset_fields(
    definition: AssetViewDefinition,
    content: str,
    fields: Mapping[str, Any],
) -> str:
    parsed = parse_asset_document(definition, content)
    _check_document_bounds(fields)
    if parsed.document_format == "json":
        native = dict(parsed.native)
        for name, value in fields.items():
            native[name] = value
        return json.dumps(native, ensure_ascii=False, indent=2) + "\n"

    native = parsed.native
    for name, value in fields.items():
        native[name] = _styled_replacement(native.get(name), value)
    stream = StringIO()
    _yaml().dump(native, stream)
    return stream.getvalue()


def _parse_json(content: str) -> Any:
    try:
        return json.loads(content)
    except json.JSONDecodeError as exc:
        raise AssetDocumentError(
            f"Invalid JSON at line {exc.lineno}, column {exc.colno}."
        ) from exc


def _parse_yaml(content: str) -> Any:
    try:
        return _yaml().load(content)
    except DuplicateKeyError as exc:
        mark = getattr(exc, "problem_mark", None)
        location = f" at line {mark.line + 1}" if mark is not None else ""
        raise AssetDocumentError(f"Duplicate YAML key{location}.") from exc
    except YAMLError as exc:
        mark = getattr(exc, "problem_mark", None)
        location = (
            f" at line {mark.line + 1}, column {mark.column + 1}"
            if mark is not None
            else ""
        )
        raise AssetDocumentError(f"Invalid YAML{location}.") from exc


def _yaml() -> YAML:
    parser = YAML(typ="rt")
    parser.allow_duplicate_keys = False
    parser.preserve_quotes = True
    parser.width = 4096
    return parser


def _document_format(definition: AssetViewDefinition) -> str:
    return "json" if definition.filename_template.endswith(".json") else "yaml"


def _styled_replacement(current: Any, value: Any) -> Any:
    if isinstance(current, ScalarString) and isinstance(value, str):
        return type(current)(value)
    if isinstance(value, dict):
        return CommentedMap(
            (str(key), _styled_replacement(None, child))
            for key, child in value.items()
        )
    if isinstance(value, list):
        return [_styled_replacement(None, child) for child in value]
    return value


def _check_document_bounds(value: Any) -> None:
    count = 0
    active: set[int] = set()

    def visit(node: Any, depth: int) -> None:
        nonlocal count
        count += 1
        if count > MAX_DOCUMENT_NODES:
            raise AssetDocumentError("Asset document contains too many values.")
        if depth > MAX_DOCUMENT_DEPTH:
            raise AssetDocumentError("Asset document nesting is too deep.")
        if not isinstance(node, (Mapping, list, tuple)):
            return
        identity = id(node)
        if identity in active:
            raise AssetDocumentError("Asset document contains a recursive alias.")
        active.add(identity)
        try:
            if isinstance(node, Mapping):
                for key, child in node.items():
                    if not isinstance(key, str):
                        raise AssetDocumentError("Asset object keys must be text.")
                    visit(child, depth + 1)
            else:
                for child in node:
                    visit(child, depth + 1)
        finally:
            active.remove(identity)

    visit(value, 0)


def _json_safe(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _json_safe(child) for key, child in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(child) for child in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)
