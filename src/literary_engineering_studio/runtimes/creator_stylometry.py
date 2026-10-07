"""Creator-only, transaction-frozen style injection and observational measurement."""
from hashlib import sha256
import json

from ..application.style.stylometry_contracts import CreatorStyleSnapshot
from ..application.style.owner_directive import read_owner_style_directive
from literary_engineering_studio_engine.public.literary import active_style_prompt_text


class CreatorStylometryMixin:
    def create_scene(self, transaction_id, brief):
        self._creator_style_snapshot(transaction_id)
        result = super().create_scene(transaction_id, brief)
        self._measure_creator_style(transaction_id, result)
        return result

    def revise_scene(self, transaction_id, brief, result, verification, review, *, attempt):
        self._creator_style_snapshot(transaction_id)
        revised = super().revise_scene(transaction_id, brief, result, verification, review, attempt=attempt)
        self._measure_creator_style(transaction_id, revised)
        return revised

    def _creator_style_snapshot(self, transaction_id):
        path = self._cache_path(transaction_id, "creator_stylometry_snapshot.json")
        if path.is_file():
            data = json.loads(path.read_text(encoding="utf-8"))
        else:
            old = tuple(path.parent.glob("prompt_assembly_v*.json"))
            provider = self._creator_style_snapshot_provider
            snapshot = provider(self._project_root) if provider and not old else CreatorStyleSnapshot()
            data = snapshot.to_dict()
            _save(path, data)
            if data["enabled"]:
                self._style_event("scene.stylometry.frozen", transaction_id, data)
        if data.get("schema") != "arcvellum/creator-stylometry-snapshot/v1":
            raise ValueError("invalid creator stylometry snapshot")
        if data["enabled"] and _digest(data["fragment_text"]) != data["content_sha256"]:
            raise ValueError("creator stylometry snapshot text hash mismatch")
        return data

    def _creator_style_text(self, transaction_id, original):
        mount = self._creator_style_snapshot(transaction_id)
        if not mount["enabled"] or mount["usage"] != "guide":
            return original
        if mount["combine"] == "replace":
            original = ""
            directive = read_owner_style_directive(self._project_root)
            if directive["active"]:
                original = str(directive["content"])
        return "\n\n".join(text for text in (original, mount["fragment_text"]) if text)

    def _author_style_reference(self, selected_reference: str) -> str:
        mounted = active_style_prompt_text(self._project_root)
        if not mounted:
            return selected_reference
        return ("### 项目已挂载文风（约束 prose 表达；交付格式由本场 Output 决定）\n"
                + mounted + "\n\n" + selected_reference)

    def _creator_style_briefing(self, transaction_id, briefing):
        path = self._cache_path(transaction_id, "creator_style_briefing.json")
        if path.is_file():
            briefing["style"] = json.loads(path.read_text(encoding="utf-8"))
            return
        mount = self._creator_style_snapshot(transaction_id)
        if mount["enabled"] and mount["usage"] == "guide":
            briefing["style"]["stylometry"] = {"content": mount["fragment_text"],
                "combine": mount["combine"], "version_id": mount["version_id"],
                "content_sha256": mount["content_sha256"]}
        _save(path, briefing["style"])

    def _measure_creator_style(self, transaction_id, result):
        mount = self._creator_style_snapshot(transaction_id)
        measure = self._creator_style_measure_provider
        if not mount["enabled"] or measure is None:
            return
        path = self._cache_path(transaction_id, "stylometry/" + _digest(result.prose) + ".json")
        if path.is_file():
            return
        try:
            report = measure(self._project_root, result.prose, mount["version_id"])
            _save(path, {"schema": "arcvellum/creator-stylometry-measurement/v1",
                "version_id": mount["version_id"], "text_sha256": _digest(result.prose), "result": json.loads(report.json_text)})
            self._style_event("scene.stylometry.measured", transaction_id, {"report_path": str(path)})
        except (ValueError, OSError) as error:
            _save(path, {"schema": "arcvellum/creator-stylometry-measurement/v1", "status": "failed",
                "version_id": mount["version_id"], "text_sha256": _digest(result.prose), "error": str(error)})
            self._style_event("scene.stylometry.measurement-failed", transaction_id, {"error": str(error)})

    def _style_event(self, event, transaction_id, payload):
        if self._event_sink:
            self._event_sink(event, {"scene_transaction_id": transaction_id, **payload})


def _digest(text):
    return sha256(text.encode("utf-8")).hexdigest()


def _save(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)
