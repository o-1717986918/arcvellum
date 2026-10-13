"""Bind original review recovery to full literary context instead of failure feedback."""
from hashlib import sha256
import json


def review_context_digest(system,protocol,context):
    semantic={key:value for key,value in context.items() if key!='delivery_feedback'}
    return sha256(json.dumps([system,protocol,semantic],ensure_ascii=False,sort_keys=True).encode()).hexdigest()


def saved_review_answer(journal,system,protocol,context):
    feedback=journal.feedback()
    if not feedback:
        return None
    state=json.loads(journal.state_path.read_text(encoding='utf-8'))
    digest=review_context_digest(system,protocol,context)
    if state.get('context_digest'):
        return feedback['previous_answer'] if state['context_digest']==digest else None
    records=journal.root.parent.parent/'sent-prompts'
    for file in records.glob('*.json'):
        binding=_legacy_binding(file,journal,system,protocol)
        if binding and binding[0]==digest and binding[1]==feedback['previous_answer']:
            return feedback['previous_answer']
    return None


def _legacy_binding(file,journal,system,protocol):
    try:
        record=json.loads(file.read_text(encoding='utf-8'))
        envelope=json.loads(record['prompt'])
        prompt=envelope.get('prompt','')
        if record.get('role')!='reviewer' or envelope.get('system_prompt')!=system or not prompt.startswith(protocol+'\n\n本次审读资料：\n'):
            return None
        context=json.loads(prompt.rsplit('本次审读资料：\n',1)[-1])
        source=journal.root/('review-'+sha256((system+prompt).encode()).hexdigest()+'.md')
        if source.is_file():
            return review_context_digest(system,protocol,context),source.read_text(encoding='utf-8')
    except (ValueError,KeyError,TypeError):
        return None
    return None
