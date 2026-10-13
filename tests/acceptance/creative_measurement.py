"""Change creative target ranges over measured profiles before an isolated run."""
from dataclasses import replace
from hashlib import sha256
import json


def configure_targets(service, project, folder, configuration_path):
    record_path = folder / 'measurement-configuration.json'
    if configuration_path is None:
        return json.loads(record_path.read_text(encoding='utf-8')) if record_path.is_file() else None
    raw = configuration_path.read_text(encoding='utf-8')
    digest = sha256(raw.encode()).hexdigest()
    if record_path.is_file():
        record = json.loads(record_path.read_text(encoding='utf-8'))
        if record['configuration_sha256'] != digest:
            raise ValueError('计量对照配置已变化，请选择新的隔离 variant。')
        return record
    transaction_root = folder / 'data/scene-transactions'
    if transaction_root.is_dir() and any(transaction_root.iterdir()):
        raise ValueError('交易已经冻结，请在新的隔离 variant 中调整计量对照。')
    configuration = json.loads(raw)
    if configuration.get('schema') != 'arcvellum/measurement-acceptance-targets/v1':
        raise ValueError('unsupported measurement acceptance configuration')
    stored = service.repository.presets(project)
    changed, rows = [], []
    requested = configuration.get('presets') or {}
    if not requested or set(requested) - {preset.preset_id for preset in stored.presets}:
        raise ValueError('请选择已有预设并填写目标范围。')
    for preset in stored.presets:
        targets = requested.get(preset.preset_id)
        if targets is None:
            changed.append(preset)
            continue
        original = service.version(project, preset.stylometry_version_id)
        controls = json.loads(original['controls_json'])
        available = {target['id']: target for target in controls['targets']}
        if not targets or set(targets) - set(available):
            raise ValueError('目标参数需来自计量台现有指标。')
        for ident, limits in targets.items():
            if set(limits) != {'min', 'max'}:
                raise ValueError('请为每个调整参数填写 min 和 max。')
            available[ident].update(limits, enabled=True)
        version = service.save_version(project, original['profile_id'], json.dumps(controls, ensure_ascii=False),
            title=preset.title + ' · 计量对照', intent=preset.literary_intent,
            dependency_json=original['dependency_json'])
        changed.append(replace(preset, stylometry_version_id=version['version_id'], active=True, usage='guide'))
        rows.append({'preset_id': preset.preset_id, 'profile_id': original['profile_id'],
                     'source_version': original['version_id'], 'version_id': version['version_id'],
                     'human_target_adjustments': targets})
    service.save_presets(project, replace(stored, enabled=True, presets=tuple(changed)), stored.revision)
    record = {'schema': 'arcvellum/measurement-acceptance-configuration/v1',
              'configuration_sha256': digest, 'configuration': configuration, 'versions': rows,
              'statistics': 'measured source profile retained; adjusted ranges are creative targets'}
    record_path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding='utf-8')
    return record
