"""Retain every natural attempt and carry failed delivery feedback into retries."""
from hashlib import sha256
import json
from pathlib import Path


class NaturalTurnStore:
    def __init__(self, root: Path, phase: str):
        self.root, self.phase = root, phase
        self.state_path = root / f"{phase}-recovery.json"

    def feedback(self):
        if not self.state_path.is_file():
            return None
        state = json.loads(self.state_path.read_text(encoding="utf-8"))
        if not state.get("active"):
            return None
        return {"attempt": state["attempt"], "issue": state["issue"],
                "previous_answer": (self.root / state["original"]).read_text(encoding="utf-8"),
                "request": "请依据已有资料和取材进度，补全本轮交付所需的信息。"}

    def answer(self, prompt, invoke):
        path = self._path(prompt)
        if path.is_file():
            return path.read_text(encoding="utf-8"), True
        answer = invoke()
        _save_text(path, answer)
        return answer, False

    def reject(self, prompt, issue):
        path = self._path(prompt)
        prior = json.loads(self.state_path.read_text(encoding="utf-8")) if self.state_path.is_file() else {}
        state = {"schema": "arcvellum/natural-delivery-recovery/v1", "active": True,
                 "attempt": prior.get("attempt", 0) + 1, "original": path.name, "issue": str(issue)}
        _save_text(path.with_suffix(".failure.json"), json.dumps(state, ensure_ascii=False, indent=2))
        _save_text(self.state_path, json.dumps(state, ensure_ascii=False, indent=2))

    def accept(self):
        if self.state_path.is_file():
            state = json.loads(self.state_path.read_text(encoding="utf-8"))
            _save_text(self.state_path, json.dumps({**state, "active": False}, ensure_ascii=False, indent=2))

    def _path(self, prompt):
        return self.root / f"{self.phase}-{sha256(prompt.encode('utf-8')).hexdigest()}.md"


def _save_text(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(text, encoding="utf-8")
    temporary.replace(path)
