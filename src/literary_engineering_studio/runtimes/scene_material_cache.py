"""Formatting-insensitive JSON identities and validated migration of completed results."""
from hashlib import sha256
import json
from .natural_transport_store import save_json


def material_source_digests(root, *, legacy_bytes=False):
    return {str(path.relative_to(root)): _source_digest(path.read_bytes(), legacy_bytes)
            for directory in ("materials", "calls") for path in sorted((root / directory).glob("*.json"))}


def material_source_bindings(root):
    """New and historical identities must describe the same captured bytes."""
    bodies = {str(path.relative_to(root)): path.read_bytes()
              for directory in ("materials", "calls") for path in sorted((root / directory).glob("*.json"))}
    return ({name: _source_digest(body, False) for name, body in bodies.items()},
            {name: _source_digest(body, True) for name, body in bodies.items()})


def _source_digest(body, legacy_bytes):
    if legacy_bytes:
        return sha256(body).hexdigest()
    try:
        value = json.loads(body.decode("utf-8"), object_pairs_hook=_unique_object)
        body = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    except (ValueError, UnicodeError):
        # Ambiguous/malformed JSON is not silently treated as equivalent data.
        pass
    return sha256(body).hexdigest()


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def cached_scene_result(current, historical, decode):
    """Historical filename must be computed from the exact current old binding."""
    for path in dict.fromkeys((current, historical)):
        if not path.is_file():
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("scene result cache must be an object")
        result = decode(payload)
        if path != current:
            save_json(current, payload)
            save_json(current.with_suffix(".reuse.json"), {
                "source": path.name, "source_sha256": sha256(path.read_bytes()).hexdigest(),
                "status": "validated-current-legacy-binding", "new_model_calls": 0})
        return result
    return None
