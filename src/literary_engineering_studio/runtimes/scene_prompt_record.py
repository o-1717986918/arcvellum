"""Persist exactly the creative input submitted to the role gateway."""
from hashlib import sha256
import json
from time import time_ns


def record_scene_prompt(runtime, transaction_id, role, prompt, *, initialization="", history=()):
    value = {"schema": "arcvellum/submitted-scene-input/v1", "role": role, "prompt": prompt,
             "system_prompt": initialization, "history": history, "recorded_at_ns": time_ns(),
             "stage": "gateway-submission", "transaction_id": transaction_id}
    value["digest"] = sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
    path = runtime._cache_path(transaction_id, f"sent-prompts/{value['recorded_at_ns']}-{value['digest'][:12]}.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
