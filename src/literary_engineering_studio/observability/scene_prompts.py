"""Project-owned transaction input, frozen style and editing evidence inspection."""
import json
from .scene_materials import material_directory
from ..application.style.transaction_bundle import TransactionStyleBundleV1


def scene_prompt_detail(data_root, transactions, transaction_id):
    transaction = next((row for row in transactions if row.transaction_id == transaction_id), None)
    if transaction is None:
        raise ValueError("scene prompt does not belong to this project")
    directory = material_directory(data_root, transaction_id)
    def read(path):
        if not path.resolve().is_relative_to(directory.resolve()):
            raise ValueError("transaction evidence escapes storage")
        return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None
    bundle = read(directory / "transaction_style_bundle.json")
    if bundle:
        TransactionStyleBundleV1.validate(bundle)
    prompts = [read(path) for path in sorted((directory / "sent-prompts").glob("*.json"))]
    edits = [read(path) for path in sorted((directory / "less-ai-tone").glob("*/report.json"))]
    measurements = [read(path) for path in sorted((directory / "stylometry").glob("*.json"))]
    stages = {}
    for edit in edits:
        stages.setdefault(edit.get("original_sha256"), []).append(edit["phase"] + " · 编辑前原稿")
        stages.setdefault(edit.get("cleaned_sha256"), []).append(edit["phase"] + " · 编辑后正文")
    measurements = [{**report, "stages": stages.get(report["text_sha256"], ["主创稿件"])} for report in measurements]
    return {"schema": "arcvellum/scene-prompts/v1", "transaction_id": transaction_id,
        "scene_id": transaction.scene_id, "style_bundle": bundle,
        "creator_briefing": read(directory / "scene_creator_briefing_v2.json"),
        "prompt_assembly": read(directory / "prompt_assembly_v2.json") or read(directory / "prompt_assembly_v1.json"),
        "tone_mount": read(directory / "less-ai-tone/mount.json"), "submitted_inputs": prompts,
        "edits": edits, "measurements": measurements,
        "input_record_status": "recorded" if prompts else "legacy-input-record-unavailable"}
