"""Retain accepted outline and chapters while a later chapter is repaired."""
from hashlib import sha256
import json
from pathlib import Path
from .natural_transport_store import save_json


def future_checkpoint(root, prompt, context, layer_id, layer_text=''):
    if root is None:
        return None
    key = sha256(json.dumps([prompt, context, layer_id, layer_text], ensure_ascii=False, sort_keys=True).encode()).hexdigest()
    return Path(root) / 'workflow/studio/future-planning-checkpoints' / key


def load_checkpoint(directory, key):
    if directory is None:
        return None
    path = directory / (sha256(key.encode()).hexdigest() + '.json')
    if not path.is_file():
        return None
    record = json.loads(path.read_text(encoding='utf-8'))
    payload = record['payload']
    actual = sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
    if actual != record['digest']:
        raise ValueError('accepted planning checkpoint digest differs')
    return payload


def save_checkpoint(directory, key, payload):
    if directory is None:
        return
    digest = sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
    save_json(directory / (sha256(key.encode()).hexdigest() + '.json'),
              {'schema':'arcvellum/planning-delivery-checkpoint/v1','payload':payload,'digest':digest})
