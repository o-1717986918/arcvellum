"""Content-checked calculation cache; references and parameters use separate keys."""
from dataclasses import asdict
from hashlib import sha256
import json
from pathlib import Path
from tempfile import NamedTemporaryFile

from ..application.style.stylometry_contracts import LabDocument


class StylometryCalculationCache:
    def __init__(self, root: Path | None):
        self.root = root

    def key(self, sources, label, lab_version):
        data = json.dumps([lab_version, label, [asdict(row) for row in sources]], ensure_ascii=False, sort_keys=True)
        return sha256(data.encode()).hexdigest()

    def read(self, key):
        if self.root is None:
            return None
        path = self.root / (key + ".json")
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if sha256(data["json_text"].encode()).hexdigest() == data["sha256"]:
                return LabDocument(data["schema"], data["json_text"])
        except (OSError, ValueError, KeyError):
            pass
        return None

    def save(self, key, document):
        if self.root is None:
            return
        self.root.mkdir(parents=True, exist_ok=True)
        data = {**asdict(document), "sha256": sha256(document.json_text.encode()).hexdigest()}
        with NamedTemporaryFile("w", dir=self.root, encoding="utf-8", delete=False) as handle:
            temporary = Path(handle.name)
            json.dump(data, handle, ensure_ascii=False)
        try:
            temporary.replace(self.root / (key + ".json"))
        finally:
            temporary.unlink(missing_ok=True)
