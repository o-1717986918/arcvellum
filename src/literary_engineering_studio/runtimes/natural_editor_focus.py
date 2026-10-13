"""Recover explicitly headed editor questions without rewriting or guessing excerpts."""
import re


def recover_creator_editor_focus(answer, payload, kind,context=None):
    if kind not in {'creator','review'}:
        return
    if not re.search(r'editor_focus|局部编辑|编辑问题|编辑核对|(?:交给|请)[^\n。]*编辑',answer):
        if payload.get('editor_focus'):
            payload['unrequested_editor_focus']=payload['editor_focus']
            payload['editor_focus']=[]
        return
    rows=_focus_rows(answer)
    if not rows:
        _drop_unstated_focus(answer,payload)
        return
    prose=str(payload.get('prose') or (context or {}).get('prose') or '')
    active,deferred=[],[]
    for issue in rows:
        issue=issue.strip()
        excerpts=_unique_quotes(issue,prose)
        focus={'issue':issue,'excerpt':next(iter(excerpts)) if len(excerpts)==1 else '', 'operation':''}
        (active if focus['excerpt'] else deferred).append(focus)
    payload['editor_focus']=active
    payload.setdefault('deferred_editor_focus',[]).extend(
        row for row in deferred if row not in payload.get('deferred_editor_focus',[]))
    payload['editor_focus_recovery']='explicit-heading-and-unique-current-prose-quote-v1'


def _drop_unstated_focus(answer,payload):
    unstated=[row for row in payload.get('editor_focus') or []
        if not isinstance(row,dict) or not row.get('issue') or row['issue'] not in answer]
    if unstated:
        payload['unrequested_editor_focus']=unstated
        payload['editor_focus']=[row for row in payload.get('editor_focus') or [] if row not in unstated]


def _unique_quotes(issue,prose):
    quoted=set(re.findall(r'“([^“”\n]+)”|「([^「」\n]+)」',issue))
    return {left or right for left,right in quoted if re.search(r'\w',left or right)
            and prose.count(left or right)==1}


def _focus_rows(answer):
    headings=list(re.finditer(r'(?m)^(?:#{1,6}[ \t]+|\*\*)[^*\n]{0,50}(?:editor_focus|局部编辑问题|编辑问题)[^\n]*$',answer))
    headings=[heading for heading in headings if '编辑问题处理' not in heading[0]]
    if len(headings)!=1:
        return []
    inline=re.fullmatch(r'\*\*[^*]+\*\*[:：]?[ \t]*(.+)',headings[0][0])
    if inline:
        return [inline[1]]
    tail=answer[headings[0].end():]
    section=re.split(r'(?m)^---[ \t]*$|^#{1,6}[ \t]+',tail,maxsplit=1)[0]
    rows=re.findall(r'(?m)^[ \t]*(?:\d+[.、][ \t]*|[-*][ \t]+)([^\n]+)$',section)
    return rows or ([section.strip()] if section.strip() else [])
