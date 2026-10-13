"""Resolve an explicit handoff field name mistakenly used as an archive target."""


def restore_handoff_targets(payload):
    delta = payload.get('scene_delta')
    if not isinstance(delta, dict):
        return payload
    handoffs = list(delta.get('next_handoff') or [])
    for key, rows in list(delta.items()):
        if key == 'next_handoff' or not isinstance(rows, list):
            continue
        retained = []
        for change in rows:
            if (isinstance(change, dict) and change.get('target_ref') in {'next_handoff', 'scene_delta.next_handoff'}
                    and isinstance(change.get('summary'), str) and change['summary'].strip()):
                handoffs.append(change['summary'])
                payload.setdefault('handoff_target_resolution', []).append({'source_field': key, 'original_record': change})
            else:
                retained.append(change)
        delta[key] = retained
    delta['next_handoff'] = handoffs
    return payload
