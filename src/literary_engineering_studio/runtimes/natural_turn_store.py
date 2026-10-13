"""Retain every natural attempt and carry failed delivery feedback into retries."""
from hashlib import sha256
import json
import re
from pathlib import Path
from .natural_transport_repair import recovery_issue


class NaturalTurnStore:
    def __init__(self, root: Path, phase: str):
        self.root, self.phase = root, phase
        self.state_path = root / f"{phase}-recovery.json"

    def feedback(self):
        if not self.state_path.is_file():
            return None
        state = json.loads(self.state_path.read_text(encoding="utf-8"))
        if not state.get("active"):
            return None
        return {"attempt": state["attempt"], "issue": state["issue"],
                "recovery":state.get('recovery',{}),
                "technical_only": state.get("technical_only", False),
                "previous_answer": (self.root / state["original"]).read_text(encoding="utf-8"),
                "request": _delivery_guidance(state["issue"])}

    def answer(self, prompt, invoke):
        path = self._path(prompt)
        if path.is_file():
            return path.read_text(encoding="utf-8"), True
        source = self._selection_replay(prompt)
        if source is not None:
            return source, True
        answer = invoke()
        _save_text(path, answer)
        return answer, False

    def _selection_replay(self, prompt):
        marker = '已提供的候选 ID：'
        if self.phase != 'creator-selection' or marker not in prompt:
            return None
        task = prompt.rsplit(marker, 1)[-1]
        for record_path in sorted((self.root.parent.parent / 'sent-prompts').glob('*.json')):
            record = json.loads(record_path.read_text(encoding='utf-8'))
            if record.get('role') != 'worker':
                continue
            envelope = json.loads(record['prompt'])
            original_prompt = envelope.get('prompt', '')
            if marker not in original_prompt or original_prompt.rsplit(marker, 1)[-1] != task:
                continue
            original = self._path(original_prompt)
            if original.is_file():
                _save_text(self._path(prompt).with_suffix('.reuse.json'), json.dumps({
                    'source': original.name, 'sent_prompt': record_path.name,
                    'task_sha256': sha256(task.encode('utf-8')).hexdigest()}, ensure_ascii=False))
                return original.read_text(encoding='utf-8')
        return None

    def referenced_scratch_source(self, prompt, answer, read_scratch):
        if self.phase != 'creator-selection' or 'v2:' in answer:
            return answer
        key = sha256((prompt+'\n'+answer).encode('utf-8')).hexdigest()
        path = self.root / ('selection-referenced-source-'+key+'.md')
        if path.is_file():
            return path.read_text(encoding='utf-8')
        sources=[]
        for relative in dict.fromkeys(re.findall(r'`([^`\n]+\.md)`',answer)):
            try:
                content=read_scratch(relative)
            except (ValueError,FileNotFoundError):
                continue
            sources.append({'path':relative,'content':content,'sha256':sha256(content.encode('utf-8')).hexdigest()})
        if not sources:
            return answer
        source=answer+'\n\n'+ '\n\n'.join('## 主创明确引用的沙盒札记：'+row['path']+'\n'+row['content'] for row in sources)
        _save_text(path,source)
        _save_text(path.with_suffix('.json'),json.dumps({'original_sha256':sha256(answer.encode('utf-8')).hexdigest(),
            'source_sha256':sha256(source.encode('utf-8')).hexdigest(),
            'references':[{key:value for key,value in row.items() if key!='content'} for row in sources]},ensure_ascii=False,indent=2))
        return source

    def reject(self, prompt, issue, *, technical_only=False, answer=None, context_digest=''):
        path = self._path(prompt)
        if technical_only or answer is not None:
            if not isinstance(answer, str) or not answer.strip():
                raise ValueError('recovery requires its preserved creative source')
            path = self.root / f"{self.phase}-pending-source-{sha256(answer.encode('utf-8')).hexdigest()}.md"
            _save_text(path, answer)
        prior = json.loads(self.state_path.read_text(encoding="utf-8")) if self.state_path.is_file() else {}
        state = {"schema": "arcvellum/natural-delivery-recovery/v1", "active": True,
                 "attempt": prior.get("attempt", 0) + 1, "original": path.name, "issue": str(issue),
                 "technical_only": technical_only}
        state['recovery']=recovery_issue(issue,answer or (path.read_text(encoding='utf-8') if path.is_file() else ''))
        if context_digest:
            state['context_digest']=context_digest
        _save_text(path.with_suffix(".failure.json"), json.dumps(state, ensure_ascii=False, indent=2))
        _save_text(self.state_path, json.dumps(state, ensure_ascii=False, indent=2))

    def accept(self):
        if self.state_path.is_file():
            state = json.loads(self.state_path.read_text(encoding="utf-8"))
            _save_text(self.state_path, json.dumps({**state, "active": False}, ensure_ascii=False, indent=2))

    def _path(self, prompt):
        return self.root / f"{self.phase}-{sha256(prompt.encode('utf-8')).hexdigest()}.md"


def _save_text(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(text, encoding="utf-8")
    temporary.replace(path)


def _delivery_guidance(issue):
    if 'review ' in issue:
        return '请回看本次同一版正文，每处直接复制一个完整句子作为证据，证据与评语分别标明；沿用当前已有问题编号，逐项说明本稿的解决或保留情况。'
    if 'known or reference' in issue:
        return '请逐项标明本次角色档案挂载是角色可知（known）还是扮演参考（reference）；角色卡来源路径记在卡的 source_refs，委托交接写本轮选定资料。'
    if 'outside the work archive' in issue or 'private name' in issue:
        return '请采用 work_archive 实际读取结果中的作品相对路径；这次选用的沙盒笔记内容通过邀请的工作语境交给伙伴。'
    return '交付已保存。仅处理明确分类和授权字段；未知错误保留断点，不重新生成整份交付。'
