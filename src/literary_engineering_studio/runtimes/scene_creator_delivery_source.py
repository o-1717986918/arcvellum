"""Retain a completed creator body when a later tool receipt becomes the final reply."""
from hashlib import sha256
import json
import re


def _has_body(text):
    return bool(re.search(r'(?m)^#{1,6}[ \t]+(?:[一二三四五六七八九十\d]+[、.．· \t-]+)?(?:最终正文|正文候选|正文)[^\n]*$',text))


def combine_creator_delivery(answer, messages):
    if _has_body(answer):
        return answer
    bodies=list(dict.fromkeys(text for text in messages if _has_body(text)))
    if len(bodies)!=1:
        return answer
    return bodies[0]+'\n\n## 主创札记 · 本轮最终说明\n\n'+answer


def _input_key(prompt):
    marker='本次创作资料：\n'
    if marker not in prompt:
        return sha256(prompt.encode()).hexdigest()
    prefix,body=prompt.rsplit(marker,1)
    try:
        context=json.loads(body)
    except ValueError:
        return sha256(prompt.encode()).hexdigest()
    context.pop('delivery_feedback',None)
    return sha256((prefix+marker+json.dumps(context,sort_keys=True,ensure_ascii=False)).encode()).hexdigest()


def recover_saved_creator_delivery(answer,prompt,data_root,archive_root):
    if _has_body(answer) and len(answer)!=20_000:
        return answer
    key=_input_key(prompt)
    for record in (data_root/'pi-conversations/worker/runs').glob('*/conversation.prompt.md'):
        try:
            value=_same_run_delivery(record,key,answer)
            if value is None:
                continue
            recovered,completed=value
            _archive_recovery(archive_root,answer,recovered,completed,record.parent/'runtime.output.log')
            return recovered
        except (ValueError,KeyError,TypeError,FileNotFoundError):
            continue
    return answer


def _same_run_delivery(record,key,answer):
    envelope=json.loads(record.read_text(encoding='utf-8'))
    if not _matching_creator_input(envelope,key):
        return None
    events=[json.loads(line) for line in (record.parent/'runtime.output.log').read_text(encoding='utf-8').splitlines() if line.strip()]
    completed=[e['data']['text'] for e in events if e.get('event')=='agent.message.completed' and isinstance(e.get('data',{}).get('text'),str)]
    finals=[e.get('data',{}).get('answer') for e in events if e.get('event')=='runner.conversation.result']
    if len(finals)==1 and _complete_preview_prefix(answer,finals[0],events):
        return finals[0],completed
    if finals!=[answer] or not completed or completed[-1]!=answer:
        return None
    recovered=combine_creator_delivery(answer,completed)
    return (recovered,completed) if recovered!=answer else None


def _matching_creator_input(envelope,key):
    return (envelope.get('schema')=='arcvellum/scene-creator/v2' and
            envelope.get('call_purpose') in {'creator','revision'} and _input_key(envelope['prompt'])==key)


def _complete_preview_prefix(answer, full, events):
    terminal=[e.get('data',{}) for e in events if e.get('event')=='runner.worker.result']
    return (len(answer)==20_000 and isinstance(full,str) and len(full)>len(answer)
            and full.startswith(answer) and bool(terminal) and terminal[-1].get('status')=='completed')


def _archive_recovery(root,answer,recovered,messages,source):
    root.mkdir(parents=True,exist_ok=True)
    digest=sha256(recovered.encode()).hexdigest()
    (root/('creator-stream-source-'+digest+'.md')).write_text(recovered,encoding='utf-8')
    (root/('creator-stream-source-'+digest+'.json')).write_text(json.dumps({
        'source_sha256':digest,'original_final_answer_sha256':sha256(answer.encode()).hexdigest(),
        'completed_message_sha256':[sha256(text.encode()).hexdigest() for text in messages],
        'runtime_output_source':str(source),'recovery':('complete-terminal-exact-preview-prefix' if recovered.startswith(answer)
            else 'one-explicit-body-same-input-and-final-answer')},ensure_ascii=False,indent=2),encoding='utf-8')
