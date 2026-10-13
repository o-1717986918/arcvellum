"""Repair only invalid fields of an already preserved extraction."""
from copy import deepcopy


class NaturalExtractionError(ValueError):
    """A technical annotation failure keeps the saved creative answer available."""
    category = 'technical'

    def __init__(self, message, *, fields=(), source_sha256='', payload=None):
        super().__init__(message)
        self.fields, self.source_sha256 = tuple(fields), source_sha256
        self.payload = payload


class NaturalSourceClarificationError(ValueError):
    """The creator's explicit source needs a semantic choice, not another annotation."""
    category = 'source-clarification'

    def __init__(self, message, *, fields=(), payload=None):
        super().__init__(message)
        self.fields, self.payload = tuple(fields), payload


def recovery_issue(error, answer=''):
    """Unknown legacy errors have no permission to repair the whole delivery."""
    from hashlib import sha256
    return {'category':getattr(error,'category','unknown'),
            'allowed_fields':list(getattr(error,'fields',())),
            'source_sha256':sha256(answer.encode()).hexdigest(), 'message':str(error)}


def repair_paths(payload, issue):
    if 'material_decisions' in issue:
        return ['/material_decisions']
    for name in ('literary_mode', 'reason'):
        if issue == f'extraction changed {name}; original natural text is preserved' and name in payload:
            return ['/' + name]
    fields = (
        ('actor candidates', '/candidates'), ('actor annotation', '/candidates'),
        ('candidate text', '/candidates'),
        ('planning chapter', '/chapter'),
        ('selected material candidate ID', '/material_decisions'),
        ('delta', '/scene_delta'), ('实际改变', '/scene_delta'), ('交接', '/scene_delta'),
        ('changed prose', '/prose'), ('card', '/material_requests'),
        ('invitation', '/material_requests'), ('author_prompt', '/material_requests'),
        ('working_context', '/material_requests'), ('style_direction', '/material_requests'),
        ('actor attachment', '/material_requests'), ('scene participant', '/material_requests'),
        ('archive attachment', '/material_requests'),
        ('mixes completed prose', '/material_requests'),
        ('tone', '/edits'), ('source anchor', '/source_references'),
        ('editor focus', '/editor_focus'), ('editor_focus', '/editor_focus'),
    )
    for token, path in fields:
        if token in issue and path.lstrip('/') in payload:
            return [path]
    for group in ('strengths','major_issues','optional_explorations','issue_progress'):
        if group.replace('_',' ') in issue or group in issue:
            return ['/'+group]
    return []


def apply_repair(existing, repair, paths):
    result = deepcopy(existing)
    if paths == ['/patches'] and isinstance(repair.get('patches'),list) and not all(
            isinstance(row,dict) and row.get('path')=='/patches' for row in repair['patches']):
        result['patches']=deepcopy(repair['patches'])
        return result
    changes = repair.get('patches')
    if changes is None:
        changes = [{'path': path, 'value': repair[path[1:]]} for path in paths if path[1:] in repair]
    if not isinstance(changes, list) or not changes:
        raise NaturalExtractionError('technical repair did not provide the requested fields')
    for change in changes:
        path = change.get('path')
        if path not in paths or 'value' not in change:
            raise NaturalExtractionError('technical repair changed a field outside the requested paths')
        _replace_path(result,path,change['value'])
    return result


def _replace_path(result,path,value):
    parts=path.lstrip('/').split('/')
    parent=result
    try:
        for part in parts[:-1]:
            parent=parent[int(part)] if isinstance(parent,list) else parent[part]
        key=int(parts[-1]) if isinstance(parent,list) else parts[-1]
        parent[key]=deepcopy(value)
    except (KeyError,IndexError,TypeError,ValueError) as error:
        raise NaturalExtractionError('technical repair path does not match frozen fields') from error
