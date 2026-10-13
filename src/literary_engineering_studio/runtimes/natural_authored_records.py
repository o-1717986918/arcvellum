"""Read explicit source-author metadata locally, preserving ambiguity and judgments."""
import json
import re
from hashlib import sha256


def authored_record(answer, key):
    records = [obj[key] for obj in json_objects(answer) if isinstance(obj.get(key), dict)]
    return records[0] if len(records) == 1 else None


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
    candidates = re.findall(r'(?ms)^```json[ \t]*\r?\n(.*?)\r?\n```[ \t]*$', answer)
    if answer.strip().startswith('{'):
        candidates.append(answer.strip())
    objects = []
    for candidate in candidates:
        try:
            obj = json.loads(candidate, object_pairs_hook=_unique)
        except (ValueError, TypeError):
            continue
        if isinstance(obj, dict):
            objects.append(obj)
    return objects


def author_field_present(answer, key, value):
    for obj in json_objects(answer):
        record = obj.get('creator_record')
        if isinstance(record, dict) and record.get(key) == value:
            return True
        if key in obj and obj[key] == value:
            return True
        for patch in obj.get('patches') or []:
            if isinstance(patch, dict) and patch.get('path') == '/' + key and patch.get('value') == value:
                return True
    return False


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('ambiguous duplicate author metadata key')
        result[key] = value
    return result
