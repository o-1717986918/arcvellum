"""Render already-authored planning records as complete literary reading notes."""
from copy import deepcopy
import re
LABELS = {
    'narrative_design': '全书叙事设计', 'chapters': '章节', 'chapter_id': '章节编号',
    'title': '标题', 'literary_task': '文学任务', 'obligation': '本章阅读任务',
    'dramatic_turn': '组织与变化', 'reader_question': '阅读兴趣',
    'future_scene_count': '未来正文单元数量', 'unit_outline': '单元目录与阅读经验',
    'scenes': '正文单元', 'name': '单元标题', 'function': '文学作用',
    'narrative_strategy': '叙述策略', 'participants': '参与人物', 'story_time': '故事时间',
    'length_weight': '相对篇幅权重', 'conflict': '处境与差异',
    'information_release': '读者获得的认识', 'consequence': '经验与延续',
    'setup_payoff_role': '前后呼应', 'rhythm_role': '组织节奏',
}


def planning_reading(value, depth=0):
    indent = '  ' * depth
    if isinstance(value, dict):
        return '\n'.join(indent + LABELS.get(key, key) + '：\n' + planning_reading(item, depth + 1)
                         for key, item in value.items() if key not in {
                             '__transport', 'source_sha256', 'source_provenance', 'reused_extraction',
                             'weight_transport_resolution', 'card_presentation_recovery'})
    if isinstance(value, list):
        return '\n'.join(indent + str(index) + '.\n' + planning_reading(item, depth + 1)
                         for index, item in enumerate(value, 1)) if value else indent + '（空）'
    return '\n'.join(indent + line for line in str(value).splitlines())


def normalize_planning_weights(payload):
    result = deepcopy(payload)
    resolutions = []
    _normalize_weights(result, '', resolutions)
    if resolutions:
        result['weight_transport_resolution'] = resolutions
    return result


def _normalize_weights(value, path, resolutions):
    if isinstance(value, dict):
        weight = value.get('length_weight')
        if isinstance(weight, str) and re.fullmatch(r'\s*[+-]?\d+(?:\.\d+)?\s*%\s*', weight):
            value['length_weight'] = float(weight.strip().removesuffix('%').strip()) / 100
            resolutions.append({'path': path + '/length_weight', 'original': weight, 'value': value['length_weight']})
        for key, item in value.items():
            _normalize_weights(item, path + '/' + key, resolutions)
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _normalize_weights(item, path + '/' + str(index), resolutions)
