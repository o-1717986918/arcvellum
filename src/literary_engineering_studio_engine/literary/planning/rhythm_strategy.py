"""Literary time-and-voice strategy alternative to legacy numeric tension."""

def literary_rhythm_strategy(value: object) -> str:
    if isinstance(value, dict) and value.get("mode") == "literary":
        return str(value.get("strategy") or "").strip()
    return ""


def rhythm_defaults(base, *layers):
    if not any(literary_rhythm_strategy(layer.get('tension_curve')) for layer in layers):
        return base
    direction = '由本段文学任务、叙述声音与时间组织选择'
    return {**base, 'paragraph_shape': direction, 'narrative_distance': direction,
            'density_mix': {key: direction for key in base['density_mix']},
            'dialogue_ratio': direction, 'action_ratio': direction, 'reflection_ratio': direction,
            'description_ratio': direction, 'summary_ratio': direction,
            'texture_variety': '发展世界、风俗、思想、情感、群体、现场与时间的文学经验。',
            'avoid_flatness': '展开本段值得读者经历的语言、趣味、认识与情感。'}
