"""Durable four-call repair budget bound to the first source, never a patched hash."""
from hashlib import sha256
import json
from pathlib import Path
from .natural_transport_store import extraction_lock, save_json

MAX_SOURCE_FIELD_REPAIRS = 4


def text_digest(text):
    return sha256(text.encode("utf-8")).hexdigest()


def _resolve_origin(root, operation, source):
    seen=set()
    while source not in seen:
        seen.add(source)
        path=root/"aliases"/(text_digest(operation+source)+".json")
        if not path.is_file():
            return source
        source=json.loads(path.read_text(encoding="utf-8"))["origin"]
    raise ValueError("repair source lineage contains a cycle; checkpoint preserved")


def _state(path, origin, operation):
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {
        "schema":"arcvellum/source-repair-budget/v1", "origin":origin, "operation":operation, "calls":[]}


class SourceRepairBudget:
    def __init__(self, root, operation, source_sha256):
        self.root=Path(root)/"repair-budgets"
        self.operation, self.source=operation, source_sha256
        self.lineage_lock=self.root/("lineage-"+text_digest(operation)+".lock")
        self._refresh()

    def _path(self, source):
        return self.root/(text_digest(self.operation+source)+".json")

    def _refresh(self):
        self.origin=_resolve_origin(self.root,self.operation,self.source)
        self.key=text_digest(self.operation+self.origin)
        self.path=self._path(self.origin)

    def _count(self, state):
        total=len(state["calls"])
        for member in state.get("lineage_members",[]):
            path=self._path(member)
            if not path.is_file():
                raise ValueError("repair lineage member checkpoint is missing")
            total+=len(json.loads(path.read_text(encoding="utf-8"))["calls"])
        return total

    def claim(self, stage, signature):
        with extraction_lock(self.lineage_lock):
            self._refresh()
            with extraction_lock(self.path.with_suffix(".lock")):
                state=_state(self.path,self.origin,self.operation)
                if self._count(state)>=MAX_SOURCE_FIELD_REPAIRS:
                    raise ValueError("original source repair budget exhausted; checkpoint preserved")
                state["calls"].append({"stage":stage,"signature":text_digest(signature)})
                save_json(self.path,state)

    def alias(self, source_sha256):
        with extraction_lock(self.lineage_lock):
            self._refresh()
            if source_sha256==self.origin:
                return
            path=self.root/"aliases"/(text_digest(self.operation+source_sha256)+".json")
            if path.is_file() and _resolve_origin(self.root,self.operation,source_sha256)!=self.origin:
                raise ValueError("repair source lineage conflicts with its original delivery")
            self._adopt_existing_claims(source_sha256)
            save_json(path,{"origin":self.origin,"source_sha256":source_sha256,"operation":self.operation})

    def _adopt_existing_claims(self, source):
        child_path=self._path(source)
        if not child_path.is_file():
            return
        child=json.loads(child_path.read_text(encoding="utf-8"))
        state=_state(self.path,self.origin,self.operation)
        members=set(state.get("lineage_members",[]))|{source}|set(child.get("lineage_members",[]))
        state["lineage_members"]=sorted(members-{self.origin})
        save_json(self.path,state)
