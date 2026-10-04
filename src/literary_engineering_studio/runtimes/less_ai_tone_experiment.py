"""An opt-in main-author editing pass between scene generation and review."""
from __future__ import annotations
from dataclasses import replace
from hashlib import sha256
import json
from pathlib import Path

from literary_engineering_studio_engine.public.literary import active_style_prompt_text
from literary_engineering_studio_engine.public.prompting import prompt_layer_spec, resolve_prompt_layer, prompt_assembly_manifest
from ..application.style.owner_directive import read_owner_style_directive
from .less_ai_tone_edits import apply_tone_edits
from .scene_natural_output import NaturalOutputProcessor, render_style

EDITOR = "experiment.less_ai_tone.editor"
EXTRACTOR = "scene.v2.transport.extractor"
SOURCE_COMMIT = "27d29232f10124db904ca9c0536d0b67cb3b2833"


class LessAiToneExperimentMixin:
    def create_scene(self, transaction_id, brief):
        mount = self._tone_mount(transaction_id)
        result = self._create_scene(transaction_id, brief)
        return self._tone_result(transaction_id, brief, result, mount, "create")

    def revise_scene(self, transaction_id, brief, result, verification, review, *, attempt):
        mount = self._tone_mount(transaction_id)
        revised = self._revise_scene(transaction_id, brief, result, verification, review, attempt=attempt)
        return self._tone_result(transaction_id, brief, revised, mount, f"revise-{attempt}")

    def _tone_mount(self, transaction_id):
        path = self._cache_path(transaction_id, "less-ai-tone/mount.json")
        if path.is_file():
            return json.loads(path.read_text(encoding="utf-8"))
        settings = self._config.get("application", {}).get("less_ai_tone_experiment", {})
        frozen_scene = tuple(path.parent.parent.glob("prompt_assembly_v*.json"))
        mount = {"schema": "arcvellum/less-ai-tone-mount/v1",
                 "enabled": settings.get("enabled") is True and not frozen_scene,
                 "source_commit": SOURCE_COMMIT}
        if mount["enabled"]:
            if self._prompt_snapshot_provider:
                snapshot = self._prompt_snapshot_provider((EDITOR, EXTRACTOR), self._project_root)
            else:
                layers = [resolve_prompt_layer(prompt_layer_spec(key)) for key in (EDITOR, EXTRACTOR)]
                snapshot = {**prompt_assembly_manifest(layers), "texts": {layer.layer_id: layer.text for layer in layers}}
            mount["texts"] = snapshot["texts"]
            mount["prompt_snapshot"] = {key: value for key, value in snapshot.items() if key != "texts"}
            directive = read_owner_style_directive(self._project_root)
            mount["style"] = "\n\n".join(text for text in (
                str(directive["content"]), active_style_prompt_text(self._project_root)) if text)
        _save(path, mount)
        return mount

    def _tone_result(self, transaction_id, brief, result, mount, phase):
        if not mount["enabled"]:
            return result
        fingerprint = _digest({"phase": phase, "result": result.to_dict(), "mount": mount})
        directory = self._cache_path(transaction_id, f"less-ai-tone/{phase}-{fingerprint[:24]}")
        report_path = directory / "report.json"
        protected = _protected(brief, result)
        if report_path.is_file():
            report = json.loads(report_path.read_text(encoding="utf-8"))
            cleaned, accepted, _ = apply_tone_edits(result.prose, report["accepted"], protected)
            if report["original"] != result.prose or cleaned != report["cleaned"] or len(accepted) != len(report["accepted"]):
                raise ValueError("less-ai-tone report does not match its frozen source")
            self._cache_hits += 1
            return _delivery(result, cleaned, accepted)
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "original.md").write_text(result.prose, encoding="utf-8")
        context = {"prose": result.prose, "scene_brief": brief.to_dict(),
                   "scene_delta": result.scene_delta.to_dict(), "author_style": mount["style"],
                   "author_intent": {"decision_summary": result.decision_summary, "decision_trace": result.decision_trace}}
        answer_path = directory / "editor-answer.md"
        if answer_path.is_file():
            answer = answer_path.read_text(encoding="utf-8")
        else:
            answer = self._tone_invoke(transaction_id, render_style(mount["texts"][EDITOR], mount["style"]),
                "请回看本场已经完成的正文，提出具体的局部修改建议。\n" + json.dumps(context, ensure_ascii=False))
            answer_path.write_text(answer, encoding="utf-8")
        processor = NaturalOutputProcessor(directory, mount["texts"][EXTRACTOR],
            lambda system, prompt: self._tone_invoke(transaction_id, system, prompt, role="reviewer"))
        payload = processor.process(answer, kind="tone", context=context)
        cleaned, accepted, rejected = apply_tone_edits(result.prose, payload.get("edits"), protected)
        (directory / "cleaned.md").write_text(cleaned, encoding="utf-8")
        report = {"schema": "arcvellum/less-ai-tone-report/v1", "transaction_id": transaction_id,
            "scene_id": brief.scene_id, "phase": phase, "input_digest": fingerprint,
            "source_commit": SOURCE_COMMIT, "original": result.prose, "cleaned": cleaned,
            "original_sha256": _text_digest(result.prose), "cleaned_sha256": _text_digest(cleaned),
            "accepted": accepted, "rejected": rejected, "summary": payload.get("summary", "")}
        _save(report_path, report)
        if self._event_sink:
            self._event_sink("scene.less-ai-tone.completed", {"scene_transaction_id": transaction_id,
                "scene_id": brief.scene_id, "accepted_count": len(accepted), "rejected_count": len(rejected),
                "report_path": str(report_path), "message": f"主创局部清理完成：{len(accepted)} 处修改，{len(rejected)} 条建议保留原文。"})
        return _delivery(result, cleaned, accepted)

    def _tone_invoke(self, transaction_id, system, prompt, role="worker"):
        return self._run(json.dumps({"schema": "arcvellum/default-conversation/v1",
            "system_prompt": system, "prompt": prompt}, ensure_ascii=False),
            role=role, transaction_id=transaction_id)


def _protected(brief, result):
    texts = list(brief.participants)
    for changes in result.scene_delta.to_dict().values():
        if isinstance(changes, list):
            texts.extend(item["evidence"] for item in changes
                         if isinstance(item, dict) and item.get("evidence"))
    return texts


def _delivery(result, prose, accepted):
    reasons = result.escalation_reasons
    if accepted:
        reasons = tuple(dict.fromkeys((*reasons, "less-ai-tone-edited-prose-review")))
    return replace(result, prose=prose, escalation_reasons=reasons)


def _text_digest(text):
    return sha256(text.encode("utf-8")).hexdigest()


def _digest(value):
    return _text_digest(json.dumps(value, ensure_ascii=False, sort_keys=True))


def _save(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)
