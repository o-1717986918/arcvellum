"""Source-author patches may modify only explicitly requested metadata paths."""
from copy import deepcopy
from .natural_transport_repair import NaturalExtractionError
from .evidence_patch_source import prose_evidence_source
from .integrity_repair_contracts import integrity_field_contract
from literary_engineering_studio_engine.public.literary import current_fact_alerts


def apply_field_patch(frozen, reply, allowed):
    patches = reply.get('patches')
    if not isinstance(patches,list) or not patches:
        raise NaturalExtractionError('field repair requires explicit patches',fields=allowed)
    result=deepcopy(frozen)
    seen=set()
    for patch in patches:
        path=patch.get('path') if isinstance(patch,dict) else None
        operation = patch.get("op","replace") if isinstance(patch,dict) else None
        if path not in allowed or path in seen or path=='/prose':
            raise NaturalExtractionError('field repair changed a field outside the requested paths',fields=allowed)
        _validate_patch_operation(patch,operation,allowed)
        seen.add(path)
        parts=path.lstrip('/').split('/')
        _set_field(result,parts,patch.get('value'),allowed,operation)
    if result.get('prose')!=frozen.get('prose'):
        raise NaturalExtractionError('field repair changed prose')
    if frozen.get('decision') and "/decision" not in allowed and result.get('decision')!=frozen['decision']:
        raise NaturalExtractionError('evidence repair changed the review decision')
    return result


def _validate_patch_operation(patch,operation,allowed):
    if operation not in {"replace","remove"} or operation=="replace" and "value" not in patch:
        raise NaturalExtractionError("field repair operation is invalid",fields=allowed)


def _set_field(result,parts,value,allowed,operation):
    try:
        parent=result
        for part in parts[:-1]:
            parent=parent[int(part)] if isinstance(parent,list) else parent[part]
        key=int(parts[-1]) if isinstance(parent,list) else parts[-1]
        if operation=="remove":
            parent.pop(key)
        else:
            parent[key]=deepcopy(value)
    except (KeyError,IndexError,TypeError,ValueError) as error:
        raise NaturalExtractionError('field repair path does not match the frozen record',fields=allowed) from error


def field_repair_task(source, payload, fields, context):
    import hashlib
    roots = {path.split('/')[1] for path in fields}
    relevant = {key:deepcopy(payload.get(key)) for key in roots}
    brief = context.get('briefing') or {}
    scoped = {key:context[key] for key in ('available_delta_targets','available_material_ids',
        'actor_card_schema','actor_system_template','actor_card_design_guidance','review_continuity','material_need_contract','material_index','material_source_evidence',
        'creation_integrity_contract','prior_delta_inventory','creator_consistency_record','fact_alerts') if key in context}
    scoped['scene_brief'] = brief.get('scene_brief',{})
    if roots.intersection({'consistency_record','scene_delta'}):
        scoped['canon_sources'] = brief.get('canon_sources', [])
        scoped['continuity_sources'] = brief.get('source_entries', [])
    if '/delivery_phase' in fields:
        scoped['source_delivery'] = source
    if any(path.endswith('/need_evidence') for path in fields):
        scoped['candidate_id_contract']='reviewed_candidate_ids、material_attachments 仅使用 available_material_ids 中已生成素材编号。档案路径和文风参照 R/S 编号不是素材候选；空库 reviewed_candidate_ids: []、existing_material_evidence: {}、material_attachments: []。mount_reasons 键须与当次保留的 archive_attachments/material_attachments 一一对应。'
    _repair_prose_context(scoped,payload,fields,context,roots)
    if scoped.get('prose') and context.get('creation_integrity_contract'):
        scoped['fact_alerts'] = current_fact_alerts(scoped['prose'])
        scoped['prose_source'] = prose_evidence_source(scoped['prose'])
    task = {'repair_protocol_version':'source-field-v3',
            'source_sha256':hashlib.sha256(source.encode()).hexdigest(),
            'frozen_fields':relevant,'frozen_review_decision':payload.get('decision'),
            'allowed_paths':list(fields),'context':scoped,
            'response_contract':{'patches':[{'path':path,'op':'replace',
                'value':_field_value_contract(path,context)} for path in fields]},
            'request':('原审读者请针对失败项核对证据，在授权路径内更正或撤回该判断，必要时更新结论与总结。'
                       '以 patches 交回，其余判断与正文保留。' if "/decision" in fields else
                       '仅以 patches 交回指定字段。已有正文、判断及其余字段已冻结；不重写全文，不重做审读。')}
    return _ordered_repair_task(task, context)


def _ordered_repair_task(task, context):
    if context.get("request_layout") == "stable-prefix-v2":
        order = ("repair_protocol_version", "request", "context", "frozen_fields", "response_contract", "allowed_paths", "frozen_review_decision", "source_sha256")
        task = {key:task[key] for key in order}
    return task


def _repair_prose_context(scoped,payload,fields,context,roots):
    if any(path.endswith('/evidence') for path in fields) or roots & {'scene_delta','decision','decision_summary',
            'consistency_record','material_decisions','strengths','optional_explorations','major_issues','issue_progress','consistency_checks'}:
        scoped['prose']=payload.get('prose') or context.get('prose','')
    if fields and all(path.endswith('/evidence') for path in fields):
        scoped['prose_source']=prose_evidence_source(scoped.pop('prose',''))


def _field_value_contract(path,context):
    if context.get('creation_integrity_contract'):
        contract = integrity_field_contract(path)
        if contract is not None:
            return contract
    if path == '/material_plan':
        return {'required_kinds':['原主创选择至少一类且不重复：actor、environment、character-description、event-narration、scene-description'],
                'reason':'这些必用伙伴对本场读者经验的具体文学理由'}
    if path == '/material_requests':
        return [{'kind':'actor、environment、character-description、event-narration 或 scene-description',
            'target':'actor 和 character-description 使用场景参与者姓名；其他类别按原委托对象',
            'purpose':'原主创本轮的取材目的', 'scene_moment':'原委托所处场景时刻',
            'cue':'原文已有的具体触发细节', 'author_prompt':'原邀约全文，须能在原文中逐字找到',
            'archive_attachments':[{'path':'作品档案实际相对路径', 'start_line':1,
                'end_line':1, 'knowledge':'known 或 reference'}],
            'working_context':'原主创明确交付的工作语境；没有则空字符串',
            'material_attachments':[], 'need_evidence':_field_value_contract('/need_evidence',context)}]
    if path == '/creative_intent':
        return {'reader_experience':'原作者读者体验，非空，至多 600 字符',
            'reader_knows':'读者当场获知的信息，至多 400 字符',
            'reader_misreads':'有意形成的误读，没有则空字符串，至多 400 字符',
            'withheld':'本场有意保留的信息，没有则空字符串，至多 400 字符'}
    if path == '/delivery_phase':
        return 'prepare 或 complete。prepare 表示本轮委托尚待实际执行，正文只保留待审候选；complete 表示这些委托是已完成过程的记录或写作说明，保留为档案，不再执行。只确认阶段，不重写正文或重新委托。'
    if path.endswith('/evidence'):
        return '返回 {"prose_sha256":context.prose_source.sha256,"prose_block":"context.prose_source.blocks 中所选现有段落 id"}，由程序逐字取回。仅选择真正支持原判断的当前正文段落，不改写引文；其余判断冻结。旧版逐字字符串仍可解析。'
    if path.endswith('/character_card'):
        from .actor_card_transport import actor_card_contract
        return actor_card_contract(context)
    if path.endswith('/knowledge'):
        return 'known 或 reference，直接枚举值；解释留在独立说明，不写入枚举值。'
    if path.endswith('/need_evidence'):
        return {'gap':'具体文学缺口','why_existing_insufficient':'已阅读资料为什么不足',
            'expected_use':'预期正文位置或间接用途','reviewed_candidate_ids':['仅当前已生成候选 ID；空库 []'],
            'existing_material_evidence':{'已阅读候选 ID':'该候选准确原文；空库 {}'},
            'mount_reasons':{'archive:索引/material:索引':'逐项现有挂载与缺口的关系；无挂载 {}'}}
    if path.endswith('/material_attachments'):
        return [{'candidate_id':'仅 available_material_ids 中现存编号；没有可用候选时整个列表 []',
            'start_char':'可选已核对字符位置','end_char':'可选已核对字符位置'}]
    return '只补交该字段的原作者值，保留对象、列表、字符串等原合同类型。'


def repair_field_values(payload,fields):
    result={}
    for path in fields:
        value=payload
        try:
            for part in path.lstrip('/').split('/'):
                value=value[int(part)] if isinstance(value,list) else value[part]
            result[path]=deepcopy(value)
        except (KeyError,IndexError,TypeError,ValueError):
            result[path]=None
    return result
