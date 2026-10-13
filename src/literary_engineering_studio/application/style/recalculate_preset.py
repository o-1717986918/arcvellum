"""Recompute selected complete references without replacing historical style versions."""
from dataclasses import replace
import json
from hashlib import sha256
from literary_engineering_studio_engine.public.literary import active_style_reference_catalog
from .initial_presets import _measurement_text
from .stylometry_contracts import CorpusTextSource


def recalculate_style_preset(service, root, preset_id, *, expected_revision):
    collection = service.repository.presets(root)
    if collection.revision != expected_revision:
        raise ValueError("文风预设已更新，请刷新后重新计算。")
    preset = next((row for row in collection.presets if row.preset_id == preset_id), None)
    if preset is None:
        raise ValueError("请先保存需要重新计算的文风预设。")
    catalog = {row['unit_id']: row for row in active_style_reference_catalog(root)['references']}
    if len(preset.reference_ids) < 2 or any(ident not in catalog for ident in preset.reference_ids):
        raise ValueError("请选择至少两条可读取的完整参照，分别用于计算与留出观察。")
    rows = [catalog[ident] for ident in preset.reference_ids]
    sources = _sources(rows, preset_id)
    profile = service.analyze(root, sources, preset.title)
    version = service.save_version(root, profile['profile_id'], json.dumps(profile['controls'], ensure_ascii=False),
                                   title=preset.title, intent=preset.literary_intent)
    replacement = replace(preset, stylometry_version_id=version['version_id'])
    updated = replace(collection, presets=tuple(replacement if row.preset_id == preset_id else row for row in collection.presets))
    service.save_presets(root, updated, expected_revision)
    return service.preset_catalog(root)


def _source(row, mode, holdout):
    original = row.get('original_sha256') or sha256((row['source_title'] + row['source_kind']).encode()).hexdigest()
    reflow = row.get('source_kind') == 'verified_literary_original' and '老殘遊記' in row['source_title']
    return CorpusTextSource(row['unit_id'].lower(), 'reference-' + original[:16], _measurement_text(row),
        split='holdout' if holdout else 'train', topic=mode, genre=mode,
        origin=row['source_kind'] + ' · ' + row['source_title'] + ' · ' + row.get('source_url', ''),
        revision=row['source_digest'] + (';gutenberg-hardwrap-reflow/v1' if reflow else ''))


def _sources(rows, mode):
    training, heldout = rows[:-1], rows[-1]
    supplied = [row for row in training if row['source_kind'] == 'user_supplied_example']
    sources = []
    if supplied:
        members = ','.join(row['unit_id'] for row in supplied)
        revision = sha256(json.dumps([row['source_digest'] for row in supplied]).encode()).hexdigest()
        sources.append(CorpusTextSource('user-' + mode, 'user-supplied-examples',
            '\n\n'.join(row['text'] for row in supplied), topic=mode, genre=mode,
            origin='完整用户样段集合：' + members, revision='members=' + members + ';sha256=' + revision))
    sources.extend(_source(row, mode, False) for row in training if row['source_kind'] != 'user_supplied_example')
    sources.append(_source(heldout, mode, True))
    return tuple(sources)
