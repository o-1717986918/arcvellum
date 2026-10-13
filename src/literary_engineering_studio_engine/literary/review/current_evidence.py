"""Current-candidate review evidence, with semantic retraction owned by the reviewer."""
from ..scene.transaction.consistency_contract import SceneConsistencyError
from .fact_alerts import current_fact_alerts

CONSISTENCY_CATEGORIES = ('time', 'quantity', 'space', 'object_state', 'identity', 'writeback')


def validate_current_review(payload, prose):
    fields = _finding_paths(payload, prose) + _progress_paths(payload)
    fields.extend(_checks(payload, prose))
    if current_fact_alerts(prose) and not _time_alert_addressed(payload):
        fields.extend(['/consistency_checks', '/major_issues'])
    if fields:
        raise SceneConsistencyError('当前稿证据未支持该问题；原审读者须重读、更正或撤回判断，不能只换引文保留旧结论。',
            tuple(dict.fromkeys([*fields, '/decision', '/summary', '/revision_instructions',
                                 '/issue_progress', '/consistency_checks'])))
    if payload.get('decision') == 'pass' and payload.get('major_issues'):
        raise SceneConsistencyError('存在主要问题时不能宣告通过；审美可选项应归入optional_explorations。',
                                    ['/decision', '/major_issues', '/optional_explorations'])


def _finding_paths(payload, prose):
    fields = []
    for group in ('strengths', 'major_issues', 'optional_explorations'):
        for index, row in enumerate(payload.get(group) or []):
            if not _finding_valid(row, group, prose):
                fields.append(f'/{group}/{index}')
    return fields


def _finding_valid(row, group, prose):
    if not isinstance(row, dict):
        return False
    evidence = row.get('evidence')
    if group == 'optional_explorations' and not evidence:
        return True
    if not _text(evidence) or evidence not in prose:
        return False
    if group != 'major_issues':
        return True
    problem = row.get('problem_excerpt')
    counter = row.get('counter_excerpt')
    return _text(problem) and problem in evidence and (not counter or _text(counter) and counter in prose)


def _progress_paths(payload):
    fields = []
    for index, row in enumerate(payload.get('issue_progress') or []):
        if not _progress_valid(row):
            fields.append(f'/issue_progress/{index}')
    return fields


def _progress_valid(row):
    if not isinstance(row, dict):
        return False
    if row.get('status') not in {'persists', 'changed'}:
        return True
    problem = row.get('problem_excerpt')
    return _text(problem) and problem in str(row.get('evidence') or '')



def _checks(payload, prose):
    checks = payload.get('consistency_checks')
    if not isinstance(checks, list):
        return ['/consistency_checks']
    seen = set()
    for check in checks:
        if not _check(check, prose, seen):
            return ['/consistency_checks']
    if seen != set(CONSISTENCY_CATEGORIES):
        return ['/consistency_checks']
    categories = {row.get('category') for row in payload.get('major_issues') or [] if isinstance(row, dict)}
    if any(row['status'] == 'issue' and row['category'] not in categories for row in checks):
        return ['/consistency_checks', '/major_issues']
    if any(row['status'] == 'uncertain' for row in checks) and payload.get('decision') != 'escalate':
        return ['/consistency_checks', '/decision']
    return []


def _check(check, prose, seen):
    if not isinstance(check, dict) or check.get('category') not in CONSISTENCY_CATEGORIES:
        return False
    category = check['category']
    if category in seen or check.get('status') not in {'clear', 'issue', 'uncertain'} or not _text(check.get('note')):
        return False
    quotes = check.get('evidence')
    if not isinstance(quotes, list) or any(not _text(quote) or quote not in prose for quote in quotes):
        return False
    seen.add(category)
    return True


def _text(value):
    return isinstance(value, str) and bool(value.strip())


def _time_alert_addressed(payload):
    return any(isinstance(row, dict) and row.get('category') == 'time'
               and row.get('status') in {'issue', 'uncertain'}
               for row in payload.get('consistency_checks') or [])
