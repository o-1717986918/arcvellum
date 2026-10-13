"""Source-backed demand records; deterministic checks do not judge literary necessity."""
from hashlib import sha256
import json
import re
from .natural_transport_repair import NaturalSourceClarificationError

NEED_MARKER = "【需求与挂载依据 v1】"
NEED_FIELDS = ("gap", "why_existing_insufficient", "expected_use")


def needs_required(layers):
    return (NEED_MARKER in layers.get("scene.v2.creator.delegation", "")
            and "scene.v2.transport.extractor" in layers)


def request_identity(request):
    return sha256(json.dumps(request.to_dict(), ensure_ascii=False, sort_keys=True).encode()).hexdigest()[:20]


def validate_need(need, request, candidates, source_candidates=None, *, relevant_candidates=None, complete_review=False):
    if not isinstance(need, dict) or any(not isinstance(need.get(k), str) or not need[k].strip()
                                         for k in NEED_FIELDS):
        raise ValueError("委托需说明具体缺口、已有材料为何不足及预期用途")
    related = related_candidates(source_candidates or {}, request) if relevant_candidates is None else set(relevant_candidates)
    reviewed = _reviewed_need(need, candidates, source_candidates, related, complete_review)
    _mount_need(need, request, reviewed)


def related_candidates(sources, request):
    return {identifier for identifier, value in sources.items()
            if value.get("kind") == request.get("kind") and _same_subjects(value.get('target'), request.get('target'))}


def _same_subjects(first, second):
    if not first and not second:
        return True
    split = lambda value: {part.strip() for part in re.split(r'[,，、;；/]', str(value or '')) if part.strip()}
    return bool(split(first).intersection(split(second)))


def _reviewed_need(need, candidates, source_candidates, related, complete_review=False):
    reviewed = need.get("reviewed_candidate_ids")
    if not isinstance(reviewed, list) or any(not isinstance(x, str) or x not in candidates for x in reviewed):
        raise ValueError("已检查候选需使用当前事务中的编号")
    if related and not set(reviewed).intersection(related):
        raise ValueError("同一对象已有回应时，继续委托需检查相关候选")
    if complete_review and not related.issubset(set(reviewed)):
        raise ValueError('继续委托前需评议同一对象的全部相关候选，不能只检查其中一条。')
    _reviewed_evidence(need, reviewed, source_candidates)
    return reviewed


def _reviewed_evidence(need, reviewed, source_candidates):
    evidence = need.get("existing_material_evidence")
    if not isinstance(evidence, dict) or set(evidence) != set(reviewed) or any(
            not isinstance(value, str) or not value.strip() for value in evidence.values()):
        raise ValueError("每个已检查候选需提供准确原文片段，不能只登记编号")
    if source_candidates is not None and any(
            excerpt not in str(source_candidates[identifier].get("text") or "")
            for identifier, excerpt in evidence.items()):
        raise ValueError("已检查材料的原文证据与当前候选不符")


def _mount_need(need, request, reviewed):
    mounts = need.get("mount_reasons")
    expected = {f"{kind}:{i}" for kind, field in (("archive", "archive_attachments"),
                ("material", "material_attachments")) for i, _ in enumerate(request.get(field) or [])}
    if not isinstance(mounts, dict) or set(mounts) != expected or any(
            not isinstance(value, str) or not value.strip() for value in mounts.values()):
        raise ValueError("每项挂载需按 archive:索引/material:索引说明与当前缺口的关系")
    selected = {row["candidate_id"] for row in request.get("material_attachments") or []}
    if not selected.issubset(set(reviewed)):
        raise ValueError("挂载前序素材前需先检查该候选")


def require_source_needs(answer, payload, context):
    if not context.get("material_need_contract"):
        return
    candidates = set(context.get("available_material_ids") or [])
    failures=[]
    fields=[]
    for index, request in enumerate(payload.get("material_requests") or []):
        need = request.get("need_evidence")
        try:
            validate_need(need, request, candidates)
            values = [*(need[k] for k in NEED_FIELDS), *need["mount_reasons"].values(),
                      *need["reviewed_candidate_ids"], *need["existing_material_evidence"].values()]
            for value in values:
                if value not in answer and json.dumps(value, ensure_ascii=False)[1:-1] not in answer:
                    raise ValueError("需求或挂载依据不在主创原文中，整理器不能代写文学理由")
        except ValueError as error:
            failures.append(str(error))
            fields.append(f"/material_requests/{index}/need_evidence")
            attachments=request.get('material_attachments') or []
            if any(item.get('candidate_id') not in candidates for item in attachments):
                fields.append(f"/material_requests/{index}/material_attachments")
                failures.append('挂载了当前素材库不存在的候选；文风参照编号不能当作已生成素材编号')
    if failures:
        raise NaturalSourceClarificationError('; '.join(dict.fromkeys(failures)),fields=tuple(fields),payload=payload)


def record_source_needs(coordinator, requests, provenance):
    if not needs_required(coordinator.layers):
        return
    source = (provenance or {}).get("source_sha256")
    if not isinstance(source, str) or len(source) != 64:
        raise ValueError("需求依据缺少原主创来源身份")
    sources = coordinator._candidate_lookup()
    candidates = set(sources)
    for index, request in enumerate(requests):
        try:
            validate_need(request.need_evidence, request.to_dict(), candidates, sources,
                          complete_review=bool(getattr(coordinator, 'integrity_contract', None)))
        except ValueError as error:
            raise NaturalSourceClarificationError(str(error),
                fields=(f"/material_requests/{index}/need_evidence",)) from error
        coordinator._write(coordinator.root / "need-evidence" / (request_identity(request) + ".json"),
            {"request": request.to_dict(), "source_sha256": source, "status": "source-validated",
             "available_candidate_ids": sorted(candidates),
             "relevant_candidate_ids": sorted(related_candidates(sources, request.to_dict())),
             "reviewed_source_digests": {identifier: sha256(str(sources[identifier].get("text") or "").encode()).hexdigest()
                for identifier in request.need_evidence["reviewed_candidate_ids"]}})


def check_saved_need(coordinator, request):
    if not needs_required(coordinator.layers):
        return
    path = coordinator.root / "need-evidence" / (request_identity(request) + ".json")
    if not path.is_file():
        raise ValueError("委托尚无经原文校验的需求与挂载依据，保存断点后再补交")
    saved = json.loads(path.read_text(encoding="utf-8"))
    if saved.get("request") != request.to_dict() or saved.get("status") != "source-validated":
        raise ValueError("保存的委托需求身份不一致")
    sources = coordinator._candidate_lookup()
    for identifier, digest in saved.get("reviewed_source_digests", {}).items():
        if identifier not in sources or sha256(str(sources[identifier].get("text") or "").encode()).hexdigest() != digest:
            raise ValueError("需求判断引用的已有材料版本发生变化，需要主创重新核对")
    # Independent invitations in one author batch share the pre-dispatch snapshot.
    validate_need(request.need_evidence, request.to_dict(), set(saved["available_candidate_ids"]), sources,
                  relevant_candidates=saved["relevant_candidate_ids"],
                  complete_review=bool(getattr(coordinator, 'integrity_contract', None)))


def validate_source_needs(payload,coordinator):
    if not coordinator or not needs_required(coordinator.layers):
        return
    sources=coordinator._candidate_lookup()
    failures,fields=[],[]
    for index,request in enumerate(payload.get('material_requests') or []):
        try:
            validate_need(request.get('need_evidence'),request,set(sources),sources,
                          complete_review=bool(getattr(coordinator, 'integrity_contract', None)))
        except ValueError as error:
            failures.append(str(error));fields.append(f'/material_requests/{index}/need_evidence')
    if fields:
        raise NaturalSourceClarificationError('; '.join(dict.fromkeys(failures)),fields=fields,payload=payload)


def repair_candidate_sources(payload,fields,sources,*,complete_review=False):
    selected=set()
    if '/material_decisions' in fields:
        selected.update(sources)
    for path in fields:
        if not path.endswith('/need_evidence'):
            continue
        request=payload['material_requests'][int(path.split('/')[2])]
        reviewed=set((request.get('need_evidence') or {}).get('reviewed_candidate_ids') or [])
        selected.update(reviewed.intersection(sources))
        related=related_candidates(sources,request)
        if complete_review or not reviewed.intersection(related):
            selected.update(related)
    return {identifier:{'text':sources[identifier]['text'],'source_sha256':sha256(sources[identifier]['text'].encode()).hexdigest()}
            for identifier in sorted(selected)}
