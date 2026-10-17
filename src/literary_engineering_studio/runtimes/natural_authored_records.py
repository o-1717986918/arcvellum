"""Read explicit source-author metadata locally, preserving ambiguity and judgments."""
import json
import re
from hashlib import sha256
from copy import deepcopy


class AuthoredRecordError(ValueError):
    def __init__(self, message, record):
        super().__init__(message)
        self.record = deepcopy(record)


def authored_record(answer, key, *, strict=False):
    objects = json_objects(answer)
    records = [(index, obj[key]) for index, obj in enumerate(objects) if isinstance(obj.get(key), dict)]
    if len(records) != 1:
        return None
    index, value = records[0]
    if key not in {'creator_record', 'review_record'}:
        return value
    try:
        record = deepcopy(value)
        if key == 'creator_record':
            _seed_disposition_alias(record)
        for obj in objects[index+1:]:
            if 'patches' in obj:
                _replay_record_patches(record, obj['patches'])
                if key == 'creator_record':
                    _patched_disposition_alias(record, obj['patches'])
        return _creator_record_layout(record) if key == 'creator_record' else record
    except (KeyError, IndexError, TypeError, ValueError) as error:
        if strict:
            raise AuthoredRecordError(str(error), record) from error
        return None


def replay_authored_patch(saved, source, reply, fields):
    """A prepared cache contains the result; replay the exact author patch, not that result."""
    expected = {'parent_source_sha256': sha256(source.encode()).hexdigest(),
                'reply_sha256': sha256(reply.encode()).hexdigest(), 'allowed_fields': list(fields)}
    if saved.get('patches') or saved.get('field_repair_provenance') not in (None, expected):
        return saved
    records = json_objects(reply)
    if len(records) != 1:
        return saved
    record = records[0]
    if isinstance(record.get('patches'), list):
        return record
    if all(path.startswith('/') and path.count('/') == 1 for path in fields):
        names = [path[1:] for path in fields]
        if set(record) == set(names) and len(names) == len(set(names)):
            return {'patches': [{'path': '/' + name, 'value': record[name]} for name in names]}
    return saved


def json_objects(answer):
    candidates = []
    for segment in answer.split('\n\n【原作者指定字段补交】\n'):
        candidates.extend(re.findall(r'(?ms)^```json[ \t]*\r?\n(.*?)\r?\n```[ \t]*$', segment))
        if segment.strip().startswith('{'):
            candidates.append(segment.strip())
    objects = []
    for candidate in candidates:
        try:
            obj = json.loads(candidate, object_pairs_hook=_unique)
        except (ValueError, TypeError):
            continue
        if isinstance(obj, dict):
            objects.append(_unwrap_patch_record(obj))
    return objects


def _unwrap_patch_record(obj):
    if len(obj) != 1:
        return obj
    key = next(iter(obj))
    wrapped = obj[key]
    if key in {'creator_record','review_record'} and isinstance(wrapped,dict) and set(wrapped)=={'patches'}:
        return wrapped
    return obj


def author_field_present(answer, key, value):
    record = authored_record(answer, 'creator_record')
    if record is not None:
        return key in record and record[key] == value
    for obj in json_objects(answer):
        if 'creator_record' in obj:
            return False
        if key in obj and obj[key] == value:
            return True
        for patch in obj.get('patches') or []:
            if isinstance(patch, dict) and patch.get('path') == '/' + key and patch.get('value') == value:
                return True
    return False


def restore_authored_consistency_layout(answer, payload):
    record = payload.get('consistency_record')
    if not isinstance(record, dict) or 'prior_delta_dispositions' in record:
        return
    authored = authored_record(answer, 'creator_record') or {}
    prior = authored.get('prior_delta_dispositions')
    if isinstance(prior, list):
        payload['consistency_record'] = {**record, 'prior_delta_dispositions': deepcopy(prior)}
        payload['consistency_layout_recovery'] = 'explicit-creator-record-outer-prior-delta-dispositions'


def _creator_record_layout(record):
    prior = record.get('prior_delta_dispositions')
    consistency = record.get('consistency_record')
    if not isinstance(prior, list) or not isinstance(consistency, dict):
        return record
    if 'prior_delta_dispositions' in consistency and consistency['prior_delta_dispositions'] != prior:
        raise ValueError('conflicting author prior-Delta disposition layouts')
    record['consistency_record'] = {**consistency, 'prior_delta_dispositions': deepcopy(prior)}
    return record


def _seed_disposition_alias(record):
    consistency = record.get('consistency_record')
    if isinstance(consistency, dict) and 'prior_delta_dispositions' not in consistency:
        prior = record.get('prior_delta_dispositions')
        if isinstance(prior, list):
            consistency['prior_delta_dispositions'] = deepcopy(prior)


def _patched_disposition_alias(record, patches):
    authority = None
    for patch in patches:
        path = patch['path']
        if path == '/prior_delta_dispositions' or path.startswith('/prior_delta_dispositions/'):
            authority = 'outer'
        elif path in {'/consistency_record', '/consistency_record/prior_delta_dispositions'} or path.startswith('/consistency_record/prior_delta_dispositions/'):
            authority = 'inner'
    if authority == 'inner':
        record.pop('prior_delta_dispositions', None)
    elif authority == 'outer' and isinstance(record.get('consistency_record'), dict):
        record['consistency_record'].pop('prior_delta_dispositions', None)
        _seed_disposition_alias(record)


def _replay_record_patches(record, patches):
    if not isinstance(patches, list) or not patches:
        raise ValueError('missing literal author patches')
    seen = set()
    for patch in patches:
        parts, operation = _record_patch_path(patch, seen)
        parent = record
        for part in parts[:-1]:
            parent = parent[int(part)] if isinstance(parent, list) and part.isdecimal() else parent[part]
        key = int(parts[-1]) if isinstance(parent, list) and parts[-1].isdecimal() else parts[-1]
        if operation == 'remove':
            parent.pop(key)
        else:
            parent[key] = deepcopy(patch['value'])


def _record_patch_path(patch, seen):
    path = patch.get('path') if isinstance(patch, dict) else None
    if not isinstance(path, str) or not path.startswith('/') or path in seen:
        raise ValueError('ambiguous author patch path')
    parts = path[1:].split('/')
    if not all(parts) or parts[0] == 'prose':
        raise ValueError('author metadata patch cannot change prose')
    seen.add(path)
    operation = patch.get('op', 'replace')
    if operation not in {'replace', 'remove'} or operation == 'replace' and 'value' not in patch:
        raise ValueError('invalid author patch operation')
    return parts, operation


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('ambiguous duplicate author metadata key')
        result[key] = value
    return result
