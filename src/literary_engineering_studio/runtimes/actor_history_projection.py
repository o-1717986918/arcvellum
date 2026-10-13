"""Current adopted actor history; indirect material stays outside actual experience."""
from typing import Any,Mapping

def _adopted_actor_history(
    rows: list[dict[str, Any]], adopted_candidate_ids: set[str] | frozenset[str],
    adopted_decisions=None,
) -> tuple[tuple[str, str], ...]:
    if not adopted_candidate_ids:
        return ()
    history = []
    for row in rows:
        for candidate in row.get("candidates") or []:
            if not isinstance(candidate, Mapping):
                continue
            if str(candidate.get("candidate_id") or "") not in adopted_candidate_ids:
                continue
            decision = (adopted_decisions or {}).get(candidate.get("candidate_id"),{})
            scoped = _scoped_actor_history(decision)
            if scoped is not None:
                history.extend(scoped)
                continue
            history.extend(_raw_actor_history(candidate))
    return tuple(history[-12:])


def _scoped_actor_history(decision):
    if decision.get("decision") != "adapt":
        return None
    if decision.get("prose_excerpt_verified") and decision.get("prose_excerpt"):
        return [("主创对应正文的叙述参考；亲历与可知事实以本轮来话和 known 档案为准",decision["prose_excerpt"])]
    if decision.get("source_excerpt_verified") and decision.get("source_excerpt"):
        return [("主创选中的改写参考；实际已发生的来话以本轮委托为准",decision["source_excerpt"])]
    if decision.get("indirect_use"):
        return []
    return [("主创登记了改写参考，但尚未登记实际经历落点；以本轮委托为准",decision.get("reason",""))]




def _raw_actor_history(candidate):
    if candidate.get('source_delivery') == 'original-v2':
        return [('主创选用的本角色上一轮表达', candidate['text'])]
    lines = []
    for key, label in (
        ("spoken", "台词"), ("first_person_action", "动作"),
        ("private_impulse", "内心冲动"),
    ):
        fragments = {'spoken': 'spoken_fragments', 'first_person_action': 'action_fragments',
                     'private_impulse': 'private_fragments'}
        value = '\n'.join(candidate.get(fragments[key]) or []) or str(candidate.get(key) or '').strip()
        if value:
            lines.append(f"{label}：{value}")
    if lines:
        return [("主创选用的本角色上一轮表达", "\n".join(lines))]
    return []
