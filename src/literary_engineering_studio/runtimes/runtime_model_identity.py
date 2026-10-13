"""Freeze selected runtime models without reading provider credentials."""
from hashlib import sha256
import json
import os
from pathlib import Path
from ..runtime.runtime_selection import runtime_for_role

ROLES = ('worker', 'reviewer', 'transport', 'character-actor', 'environment-writer',
         'character-describer', 'event-narrator', 'scene-describer')


def runtime_model_identity(config):
    settings_by_runtime = {}
    catalogs = {}
    rows = {}
    for role in ROLES:
        runtime = runtime_for_role(config, role)
        if runtime not in settings_by_runtime:
            settings_by_runtime[runtime] = (config.get('agent_runners') or {}).get(runtime) or {}
            catalogs[runtime] = _model_catalog(settings_by_runtime[runtime]) if runtime == 'pi-worker' else {}
        rows[role] = _role_identity(role, runtime, settings_by_runtime[runtime], catalogs[runtime])
    return {'schema': 'arcvellum/runtime-model-binding/v1', 'roles': rows}


def _model_catalog(settings):
    configured = settings.get('auth_path')
    directory = Path(configured).expanduser().parent if configured else Path(
        os.environ.get('PI_CODING_AGENT_DIR') or Path.home() / '.pi' / 'agent')
    path = directory / 'models.json'
    return json.loads(path.read_text(encoding='utf-8')) if path.is_file() else {}


def _role_identity(role, runtime, settings, catalog):
    model = (settings.get('models') or {}).get(role) or settings.get('model') or ''
    row = {'runtime': runtime, 'model': model}
    provider_id, _, model_id = str(model).partition('/')
    provider = (catalog.get('providers') or {}).get(provider_id)
    if isinstance(provider, dict):
        definitions = [_model_definition(item)
                       for item in provider.get('models') or [] if item.get('id') == model_id]
        safe = {'api': provider.get('api'), 'baseUrl': provider.get('baseUrl'), 'models': definitions}
        row['configured_definition_sha256'] = sha256(json.dumps(
            safe, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
    return row


def _model_definition(item):
    fields = ('id', 'reasoning', 'input', 'contextWindow', 'maxTokens', 'compat', 'samplingParams')
    value = {key: item.get(key) for key in fields}
    return value
