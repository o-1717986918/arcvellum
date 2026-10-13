"""Immutable style identity shared by creative roles in a scene transaction."""
from dataclasses import dataclass, field
from hashlib import sha256
import json
from typing import Any


def bundle_digest(value: Any) -> str:
    return sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


@dataclass(frozen=True)
class TransactionStyleBundleV1:
    transaction_id: str
    preset_revision: int
    selection: dict[str, Any]
    style: dict[str, Any]
    measurement: dict[str, Any]
    tone_enabled: bool
    material_scope: dict[str, Any] = field(default_factory=dict)

    def to_dict(self):
        value = {"schema": "arcvellum/transaction-style-bundle/v1", **self.__dict__}
        return {**value, "digest": bundle_digest(value)}

    @staticmethod
    def validate(value):
        if (value.get("schema") != "arcvellum/transaction-style-bundle/v1"
                or value.get("digest") != bundle_digest({key: item for key, item in value.items() if key != "digest"})):
            raise ValueError("transaction style bundle digest/schema mismatch")
        return value
