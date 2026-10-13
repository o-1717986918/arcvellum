"""Reuse only equal actual literary inputs; bookkeeping changes do not create a new call."""
from hashlib import sha256
import json


def literary_request(request):
    return {key: value for key, value in request.items() if key != "need_evidence"}


def input_identity(call, scene_id, layers):
    value = [scene_id, call.role, call.initialization, call.prompt, call.history,
             call.initialization_answer, call.attachment_manifest, call.response_mode,
             layers.get("scene.v2.transport.extractor", ""), "material-response-v1"]
    return sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def reuse_equal_input(coordinator, request_key, digest, request):
    for path in sorted((coordinator.root / "calls").glob("*.json")):
        saved = json.loads(path.read_text(encoding="utf-8"))
        if saved.get("input_identity") == digest and saved.get("invoked") is True:
            coordinator._write(coordinator.root / "reused-inputs" / (request_key + ".json"),
                {"request": request.to_dict(), "input_identity": digest,
                 "source_call": path.name, "request_id": saved["request_id"],
                 "status": "reused-identical-literary-input", "new_model_calls": 0})
            return saved["candidates"]
    return None
