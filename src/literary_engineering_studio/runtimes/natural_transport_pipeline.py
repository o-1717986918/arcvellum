"""Local-first natural delivery, versioned source references and durable reuse."""
from copy import deepcopy
from hashlib import sha256
import json
import re
from pathlib import Path

from literary_engineering_studio_engine.public.literary import natural_source_index
from .pi_scene_payload import _answer_payload
from .natural_transport_context import extraction_context
from .natural_local_delivery import local_delivery, local_cards, local_creator_fields
from .natural_reference_delivery import decode_reference_delivery, hydrate_local_cards, PartialReferenceError
from .natural_transport_repair import NaturalExtractionError, NaturalSourceClarificationError, repair_paths, apply_repair
from .natural_transport_store import extraction_lock, save_json, save_text
from .natural_transport_task import extraction_task
from .natural_actor_transport import seed_actor_response, finish_actor_fields
from .source_repair_budget import SourceRepairBudget
from .transport_json_closure import recover_object_terminator

PROCESSOR_VERSION = 'cost-recovery-v4.44'

class NaturalTransportPipeline:
    def __init__(self, root, system, invoke, prepare, contracts):
        self.root, self.system, self.invoke = root, system, invoke
        self.prepare, self.contracts = prepare, contracts

    def process(self, answer, kind, context, reuse_only=False):
        if not answer.strip() or len(answer) > 160_000:
            raise ValueError('natural response is empty or exceeds the transport budget')
        index = natural_source_index(answer)
        directory = self.root / 'natural-answers' / index['sha256']
        with extraction_lock(directory / 'source.lock'):
            _preserve_original(directory, answer, index)
        semantic = extraction_context(kind, context)
        fingerprint = sha256(json.dumps([PROCESSOR_VERSION, kind, semantic, self.system, self.contracts.get(kind)],
                                        ensure_ascii=False, sort_keys=True).encode()).hexdigest()
        with extraction_lock(directory / (fingerprint + '.lock')):
            return self._locked(answer, kind, context, semantic, index, directory, fingerprint, reuse_only)

    def _locked(self, answer, kind, context, semantic, index, directory, key, reuse_only):
        cache = directory / (key + '.json')
        if cache.is_file():
            saved = json.loads(cache.read_text(encoding='utf-8'))
            try:
                payload = self.prepare(answer, _merge_fields(saved,local_creator_fields(answer,kind,context)), kind, context)
                return self._record(payload, directory, key, kind, 'reused', 0)
            except NaturalSourceClarificationError:
                raise
            except ValueError as error:
                save_json(directory / (key + '.invalid-cache.json'), {'payload': saved, 'issue': str(error)})
        local = self._local(answer, kind, context)
        if local is not None:
            save_json(cache, local)
            return self._record(local, directory, key, kind, 'local', 0)
        prior = self._prior(answer, kind, context, directory)
        if prior is not None:
            save_json(cache, prior)
            return self._record(prior, directory, key, kind, 'recovered', 0)
        if reuse_only:
            detail = '; '.join(dict.fromkeys(self.recovery_issues))
            raise NaturalExtractionError('saved source has no valid extraction for the current context' + (': ' + detail if detail else ''))
        blocked=directory/(key+'.blocked.json')
        if blocked.is_file():
            prior=json.loads(blocked.read_text(encoding='utf-8'))
            raise NaturalExtractionError('unchanged failed extraction is preserved: '+prior['issue'],
                                         fields=prior.get('fields',()),source_sha256=index['sha256'],payload=prior.get('payload'))
        self.calls = 0
        try:
            payload, calls = self._extract(answer, kind, context, semantic, index, directory, key)
        except Exception as error:
            if isinstance(error,NaturalExtractionError):
                save_json(blocked,{'issue':str(error),'fields':list(getattr(error,'fields',())),
                                  'source_sha256':index['sha256'],'contract_sha256':key,
                                  'payload':getattr(error,'payload',None)})
            self._record({}, directory, key, kind, 'failed', self.calls, error=str(error))
            raise
        save_json(cache, payload)
        return self._record(payload, directory, key, kind, 'model' if calls == 1 else 'repaired', calls)

    def _local(self, answer, kind, context):
        candidate = local_delivery(answer, kind, context)
        if candidate is None:
            candidate = _whole_json(answer, embedded=kind=='field-repair')
        if candidate is None:
            return None
        try:
            return self.prepare(answer, candidate, kind, context)
        except NaturalSourceClarificationError:
            raise
        except ValueError:
            return None

    def _prior(self, answer, kind, context, directory):
        self.recovery_issues = []
        prepared = self._saved_prepared(answer,kind,context,directory)
        if prepared is not None:
            return prepared
        partial = self._saved_partials(answer,kind,context,directory)
        if partial is not None:
            return partial
        paths = sorted(directory.glob('*.extraction*.md'), key=lambda path: path.stat().st_mtime, reverse=True)
        for path in paths:
            try:
                raw = _extraction_payload(path.read_text(encoding='utf-8'), record_path=path)
                if '[NATURAL_TASK_FIELDS_V2]' in self.system:
                    raw = seed_actor_response(raw, answer, kind, context)
                candidate = decode_reference_delivery(raw, answer)
                candidate = _merge_fields(candidate, local_creator_fields(answer, kind,context))
                candidate = hydrate_local_cards(candidate, local_cards(answer, context))
                candidate = self._actor_fields(candidate,answer,kind,context)
                prepared = self.prepare(answer, candidate, kind, context)
                prepared["reused_extraction"] = path.name
                return prepared
            except NaturalSourceClarificationError as error:
                if error.payload is None:
                    error.payload=deepcopy(candidate)
                raise
            except (ValueError, KeyError, TypeError) as error:
                self.recovery_issues.append(str(error))
                continue
        return None

    def _saved_partials(self,answer,kind,context,directory):
        for checkpoint in sorted(directory.glob('*.partial.json'),key=lambda p:p.stat().st_mtime,reverse=True):
            saved=json.loads(checkpoint.read_text(encoding='utf-8'))
            partial,paths=saved.get('payload'),saved.get('paths')
            if not isinstance(partial,dict) or not paths:
                continue
            prefix=checkpoint.name.removesuffix('.partial.json')
            for extraction in sorted(directory.glob(prefix+'.extraction*.md'),key=lambda p:p.stat().st_mtime,reverse=True):
                try:
                    decoded=decode_reference_delivery(_extraction_payload(extraction.read_text(encoding='utf-8'),record_path=extraction),answer)
                    candidate=apply_repair(partial,decoded,paths)
                    candidate=_merge_fields(candidate,local_creator_fields(answer,kind,context))
                    candidate=hydrate_local_cards(candidate,local_cards(answer,context))
                    candidate=self._actor_fields(candidate,answer,kind,context)
                    return self.prepare(answer,candidate,kind,context)
                except NaturalSourceClarificationError:
                    raise
                except (ValueError,KeyError,TypeError) as error:
                    self.recovery_issues.append(str(error))
        return None

    def _saved_prepared(self,answer,kind,context,directory):
        paths = [path for path in directory.glob("*.json") if len(path.stem)==64
                 and all(char in "0123456789abcdef" for char in path.stem)]
        for path in sorted(paths,key=lambda value:value.stat().st_mtime,reverse=True):
            try:
                payload=json.loads(path.read_text(encoding="utf-8"))
                payload=_merge_fields(payload,local_creator_fields(answer,kind,context))
                payload=hydrate_local_cards(payload,local_cards(answer,context))
                return self.prepare(answer,self._actor_fields(payload,answer,kind,context),kind,context)
            except NaturalSourceClarificationError:
                raise
            except (ValueError,KeyError,TypeError) as error:
                self.recovery_issues.append(str(error))
        return None

    def _extract(self, answer, kind, context, semantic, index, directory, key):
        fields = local_creator_fields(answer, kind,context)
        cards = local_cards(answer, context)
        task = extraction_task(kind, self.contracts[kind], semantic, index, answer, fields, cards)
        save_json(directory / (key + '.local-fields.json'), {'fields': fields, 'cards': cards})
        partial, issue, paths = {}, '', None
        checkpoint = directory / (key + '.partial.json')
        if checkpoint.is_file():
            saved = json.loads(checkpoint.read_text(encoding='utf-8'))
            partial, issue, paths = saved.get('payload') or {}, saved.get('issue', ''), saved.get('paths')
            task = extraction_task(kind, self.contracts[kind], semantic, index, answer, fields, cards,
                                   paths=paths, issue=issue)
        for attempt in range(2):
            self._reserve_retry(kind, context, index, task, paths, partial, attempt)
            self.calls += 1
            response = self.invoke(self.system, json.dumps(task, ensure_ascii=False))
            sequence = len(list(directory.glob(key + '.extraction*.md'))) + 1
            suffix = f'.extraction-{sequence}.md'
            save_text(directory / (key + suffix), response)
            try:
                raw = seed_actor_response(_extraction_payload(response, record_path=directory/(key+suffix)), answer, kind, context)
                decoded = decode_reference_delivery(raw, answer)
                partial = apply_repair(partial, decoded, paths) if paths else _merge_fields(decoded, fields)
                partial = hydrate_local_cards(partial, cards)
                partial = self._actor_fields(partial,answer,kind,context)
                prepared = self.prepare(answer, partial, kind, context)
                _save_field_checkpoints(directory,key,answer,prepared,[])
                return prepared, attempt+1
            except NaturalSourceClarificationError as error:
                if error.payload is None:
                    error.payload=deepcopy(partial)
                raise
            except (ValueError, KeyError, TypeError) as error:
                issue = str(error)
                if isinstance(error.__cause__, json.JSONDecodeError):
                    cause = error.__cause__
                    issue += f'; JSON syntax: {cause.msg} at line {cause.lineno}, column {cause.colno}'
                save_json(directory / (key + suffix + '.failure.json'), {'issue': issue})
                partial, paths = _repair_state(partial, fields, error)
                if partial and not paths:
                    _save_field_checkpoints(directory,key,answer,partial,[])
                    raise NaturalExtractionError(issue,source_sha256=index["sha256"]) from error
                task = extraction_task(kind, self.contracts[kind], semantic, index, answer, fields, cards,
                                       paths=paths, issue=issue)
                if partial:
                    save_json(checkpoint, {'payload': partial, 'issue': issue, 'paths': paths})
        _save_field_checkpoints(directory,key,answer,partial,paths or [])
        raise NaturalExtractionError(issue,fields=paths or (),source_sha256=index['sha256'],payload=partial)

    def _reserve_retry(self, kind, context, index, task, paths, partial, attempt):
        if not (attempt or paths or kind == "field-repair"):
            return
        operation = context.get("repair_operation", kind)
        source = context.get("parent_source_sha256", index["sha256"])
        try:
            SourceRepairBudget(self.root, operation, source).claim("transport", json.dumps(task, ensure_ascii=False, sort_keys=True))
        except ValueError as error:
            raise NaturalExtractionError(str(error), fields=paths or (), source_sha256=index["sha256"], payload=partial) from error

    def _actor_fields(self,payload,answer,kind,context):
        return finish_actor_fields(payload,answer,kind,context) if '[NATURAL_TASK_FIELDS_V2]' in self.system else payload

    @staticmethod
    def _record(payload, directory, key, kind, mode, calls, *, error=''):
        if payload:
            with (directory/'original.source.txt').open(encoding='utf-8',newline='') as stream:
                original = stream.read()
            _save_field_checkpoints(directory,key,original,payload,[])
        path = directory / (key + '.transport.json')
        previous = json.loads(path.read_text(encoding='utf-8')) if path.is_file() else {}
        report = {'schema': 'arcvellum/natural-transport/v1', 'operation': kind, 'mode': mode,
                  'initial_mode': previous.get('initial_mode', mode),
                  'model_calls': previous.get('model_calls', 0) + calls,
                  'reuse_count': previous.get('reuse_count', 0) + int(mode == 'reused'),
                  'requested_thinking': 'off' if calls or previous.get('model_calls') else None,
                  'source_sha256': directory.name, 'record_id': key, 'error': error}
        save_json(path, report)
        return {**payload, '__transport': {**report, 'model_calls': calls}}


def _whole_json(answer, *, embedded=False):
    text = answer.strip()
    if embedded:
        blocks=re.findall(r'(?ms)^```json[ \t]*\r?\n(.*?)\r?\n```[ \t]*$',text)
        if len(blocks)==1:
            text=blocks[0].strip()
    if text.startswith('```json') and text.endswith('```'):
        text = text[7:-3].strip()
    if text.startswith('{') and text.endswith('}'):
        try:
            result = json.loads(text)
            return result if isinstance(result, dict) else None
        except ValueError:
            pass
    return None


def _extraction_payload(answer, *, record_path=None):
    explicit=_whole_json(answer,embedded=True)
    if explicit is not None:
        return explicit
    try:
        return _answer_payload(answer)
    except ValueError:
        recovered = recover_object_terminator(answer) if record_path is not None else None
        if recovered is None:
            raise
        payload, receipt = recovered
        save_json(record_path.with_suffix('.syntax-recovery.json'),
                  {**receipt, 'source_sha256': record_path.parent.name})
        return payload


def _merge_fields(decoded, fields):
    local = deepcopy(fields)
    return {**decoded, **local}


def _repair_state(partial, fields, error):
    if isinstance(error, PartialReferenceError):
        return _merge_fields(error.payload, fields), error.paths
    if getattr(error,'fields',None):
        return partial,list(error.fields)
    return partial, repair_paths(partial, str(error)) if partial else None


def _preserve_original(directory, answer, index):
    original = directory / 'original.source.txt'
    if original.is_file():
        with original.open(encoding='utf-8', newline='') as handle:
            saved = handle.read()
        if saved != answer:
            raise NaturalExtractionError('preserved natural original changed')
    else:
        save_text(original, answer)
    if not (directory / 'original.md').is_file():
        save_text(directory / 'original.md', answer)
    target = directory / 'source-index.json'
    if not target.is_file():
        save_json(target, {**index, 'source_file': 'original.source.txt'})


def _save_field_checkpoints(directory,key,answer,payload,invalid):
    for field in ('prose','scene_delta','material_requests','material_decisions'):
        if field not in payload or '/'+field in invalid:
            continue
        if field=='prose' and (not isinstance(payload[field],str) or
                payload[field] not in answer and json.dumps(payload[field],ensure_ascii=False)[1:-1] not in answer):
            continue
        save_json(directory/(key+'.field-'+field+'.json'),
                  {'source_sha256':directory.name,'field':field,'value':payload[field],
                   'validation':'source-match-only' if field=='prose' else 'not-in-failed-field-set'})
