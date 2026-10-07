"""Package a complete bounded natural response without rewriting literary source text."""
import re

_PLAIN_ROLES = {'environment-writer','character-describer','scene-describer'}


def whole_material_response(answer, context):
    role = context.get('role')
    if not answer.strip() or len(answer) > 2400 or role not in _PLAIN_ROLES | {'character-actor'}:
        return None
    candidate = {'text':answer,'focus':'本次委托的完整自然回应'}
    if role == 'character-actor':
        # An explicit first-person narrative paragraph is a literal action excerpt.
        unquoted = re.split(r'“[^”]*”|「[^」]*」|『[^』]*』|"[^"\n]*"',answer)
        paragraphs = [text for region in unquoted for text in re.split(r'\n\s*\n',region)]
        action = next((text for text in paragraphs if len(text)<=1200
            and re.search(r'我(?:把|将|伸|拿|按|拢|放|握|推|转|望|抬|低|坐|站|蹲|摸|扶|揣|收|点|踩|拧|走|停|扯|往|朝)',text)),None)
        if not action:
            return None
        candidate.update(first_person_action=action,spoken='',private_impulse='')
    return {'candidates':[candidate],'source_delivery':'whole-natural-response',
            'source_annotations':'literal-first-person-paragraph' if role=='character-actor' else 'none'}
