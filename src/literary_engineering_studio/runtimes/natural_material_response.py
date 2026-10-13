"""Package a complete bounded natural response without rewriting literary source text."""

_PLAIN_ROLES = {'environment-writer','character-describer','scene-describer'}


def whole_material_response(answer, context):
    role = context.get('role')
    if not answer.strip() or len(answer) > 2400 or role not in _PLAIN_ROLES:
        return None
    candidate = {'text':answer,'focus':'本次委托的完整自然回应'}
    return {'candidates':[candidate],'source_delivery':'whole-natural-response',
            'source_annotations':'none'}
