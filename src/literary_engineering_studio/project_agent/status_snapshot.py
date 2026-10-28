"""Small control-plane view with explicit paths to full literary evidence."""
from collections.abc import Mapping


def status_snapshot(diagnosis, progress):
    run = diagnosis.get('run') or {}
    run_fields = ('run_id', 'status', 'mode', 'current_route', 'current_task_id',
                  'tasks_completed', 'failures', 'stop_reason', 'last_error', 'updated_at')
    decisions = diagnosis.get('pending_decisions') or []
    decision_fields = ('choice_id', 'decision_id', 'id', 'title', 'kind', 'severity')
    return {
        'work_id': diagnosis['work_id'], 'focus': 'status', 'view': 'control-summary-v1',
        **{key: diagnosis[key] for key in ('classification', 'recoverable', 'recommended_tool',
            'plan_alignment', 'unmigrated_formal_work') if key in diagnosis},
        'run': {key: run[key] for key in run_fields if key in run},
        'progress': {key: progress[key] for key in
                     ('overall_percent', 'completed_scenes', 'total_scenes') if key in progress},
        'pending_decisions': [{key: item[key] for key in decision_fields if key in item}
                              for item in decisions if isinstance(item, Mapping)],
        'next_actions': list(diagnosis.get('next_actions') or [])[:4],
        'route_audits': list(diagnosis.get('route_audits') or [])[:4],
        'details': {
            'diagnosis': 'project_diagnose', 'controls': 'project_controls(section=...)',
            'story': 'project_overview(focus=story)', 'archive': 'project_archive_read',
            'note': '这是状态摘要。做文学判断、处理决策或修改前，读取相应完整资料；摘要不能替代正式证据。',
        },
    }
