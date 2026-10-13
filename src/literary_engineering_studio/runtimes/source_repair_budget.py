"""Durable four-call repair budget bound to the first source, never a patched hash."""
from hashlib import sha256
import json
from pathlib import Path
from .natural_transport_store import extraction_lock, save_json

MAX_SOURCE_FIELD_REPAIRS = 4


def text_digest(text):
    return sha256(text.encode("utf-8")).hexdigest()


class SourceRepairBudget:
    def __init__(self, root, operation, source_sha256):
        self.root = Path(root) / "repair-budgets"
        self.operation = operation
        alias = self.root / "aliases" / (text_digest(operation + source_sha256) + ".json")
        self.origin = json.loads(alias.read_text(encoding="utf-8"))["origin"] if alias.is_file() else source_sha256
        self.key = text_digest(operation + self.origin)
        self.path = self.root / (self.key + ".json")

    def claim(self, stage, signature):
        with extraction_lock(self.path.with_suffix(".lock")):
            state = json.loads(self.path.read_text(encoding="utf-8")) if self.path.is_file() else {
                "schema":"arcvellum/source-repair-budget/v1", "origin":self.origin, "operation":self.operation, "calls":[]}
            if len(state["calls"]) >= MAX_SOURCE_FIELD_REPAIRS:
                raise ValueError("original source repair budget exhausted; checkpoint preserved")
            state["calls"].append({"stage":stage,"signature":text_digest(signature)})
            save_json(self.path,state)

    def alias(self, source_sha256):
        path = self.root / "aliases" / (text_digest(self.operation + source_sha256) + ".json")
        with extraction_lock(path.with_suffix(".lock")):
            if path.is_file() and json.loads(path.read_text(encoding="utf-8"))["origin"] != self.origin:
                raise ValueError("repair source lineage conflicts with its original delivery")
            save_json(path,{"origin":self.origin,"source_sha256":source_sha256,"operation":self.operation})
