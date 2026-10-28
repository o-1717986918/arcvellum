"""Stable technical contracts precede variable original text and repair feedback."""
from copy import deepcopy
from .actor_card_transport import actor_card_contract
from .natural_source_view import model_source_view


def extraction_task(kind, contract, context, index, answer, fields, cards, *, paths=None, issue=''):
    if kind == 'creator' and context.get('selection_only') and paths:
        paths = ['/material_decisions']
    remaining = _requested_fields(_contract(kind,contract,context),fields,paths)
    task = {'operation': kind, 'task_contract': remaining,
            'source_reference_contract': {'index_unit': 'unicode-codepoint', 'end_exclusive': True,
                                          'digest_policy': 'source_sha256 元数据由程序绑定当前保存原文，无需返回；若返回只能为 source_index.sha256 的准确字符串，不能为 $source 引用、原文内容或自算摘要。',
                                          'long_fields': '原文引用，程序逐字重建'},
            'remaining_fields': list(remaining),
            'context': context,
            'known_cards': {target: {'schema': card['schema'], 'target': target} for target, card in cards.items()},
            'local_fields': list(fields),
            **model_source_view(index, answer)}
    task['delivery_guidance'] = _guidance(kind, context)
    if kind=='review':
        task['delivery_guidance']+=' evidence 直接逐字复制 context.prose 的连续正文，不使用 source_index/$source 定位正文；该索引只定位审读意见自身。不要把未明确委托局部编辑的判断登记为 editor_focus。'
        task['delivery_guidance']+=' 本轮判断、总结和修订方向只登记 source_text；历史问题仅供编号关联，不得把上一轮总结或修订要求当作本轮意见。'
    if fields.get('prose') == '':
        task['delivery_guidance'] += ' 本次原文明示准备邀请，prose 已由程序登记为空，补齐当轮邀请。'
    if kind == 'creator' and 'material_requests' in remaining:
        task['actor_card_contract'] = actor_card_contract(context)
    if kind == 'material':
        task['annotation_contract'] = {'kind': 'spoken/first_person_action/private_impulse',
                                        'text': '原文引用；同类可以有多个片段，沿原文顺序列出'}
        if context.get('role') == 'character-actor':
            task['actor_annotation'] = '只标注目标人物本人实际说出的言语、第一人称动作与私人冲动，保留完整回应与原文顺序。'
    if paths:
        task['repair_paths'] = paths
    if issue:
        task['transport_feedback'] = {'issue': issue, 'request':
            '补交 repair_paths 对应的字段，成功记录由程序沿用。' if paths else
            '上一份交付不是有效的完整 JSON 对象。只纠正 JSON 技术格式，重新交付完整对象；'
            '保持原文引用和文学判断不变，不要重写 source_text，不要输出解释。'}
    return _stable_task_order(task)


def _stable_task_order(task):
    # Contracts, requested fields and feedback still travel intact after source.
    stable = ('operation', 'source_reference_contract', 'delivery_guidance',
              'annotation_contract', 'actor_annotation', 'context', 'source_text', 'source_index')
    return {**{key: task[key] for key in stable if key in task},
            **{key: value for key, value in task.items() if key not in stable}}


def _requested_fields(contract, fields, paths):
    if paths and any('/' in path[1:] for path in paths):
        return {'patches':[{'path':path,'value':'只逐字恢复该字段；evidence 只复制 context.prose 中的正文文字。其他字段由程序冻结。'} for path in paths]}
    pending={key:value for key,value in contract.items() if key not in fields}
    if paths:
        return {key:value for key,value in pending.items() if '/'+key in paths}
    return pending


def _contract(kind, contract, context):
    result = deepcopy(contract)
    if kind == 'creator' and context.get('selection_only'):
        return {'material_decisions': result['material_decisions']}
    if kind == 'card':
        return {'card': actor_card_contract(context)}
    if kind == 'creator':
        result['material_requests'][0]['character_card'] = '已有本地卡时使用 null；程序按人物恢复原卡'
        result['material_requests'][0]['working_context'] = (
            '本次委托的当前语境原文片段；未另列语境时为空。逐字引用相关片段，最多 6000 字符；不得引用整份筹备稿。')
        if context.get('available_material_ids') == []:
            result['material_decisions'] = []
    if kind == 'material':
        item = result['candidates'][0]
        role = context.get('role')
        if role == 'character-actor':
            result['candidates'] = [{'focus': '本角色这一轮回应的主题', 'annotations': [
                {'kind': 'spoken/first_person_action/private_impulse', 'text': '本角色的连续原文引用'}]}]
        else:
            for key in ('spoken', 'first_person_action', 'private_impulse'):
                item.pop(key, None)
            if role != 'event-narrator':
                item.pop('basis', None); item.pop('source_note', None)
    if kind=='review':
        for key in ('strengths','major_issues','optional_explorations','issue_progress'):
            result[key][0]['evidence']='直接复制 context.prose 的连续正文字符串；不要使用 $source 或 source_index 的审读原文编号。'
    return result


def _guidance(kind, context):
    if kind == 'creator' and context.get('selection_only'):
        return '本次仅登记取舍札记中的 material_decisions，逐项使用原文明示且在实际候选目录中的编号、use/adapt/discard/defer 和文学理由。正文与其他成功字段由程序沿用。'
    if kind == 'creator':
        return ('先按原文明示的阶段登记。准备阶段登记当轮待执行的 material_requests，prose 为空；'
                '完成阶段以 prose 登记完整正文，material_requests 为空，旧邀请回顾归入 decision_summary。'
                'available_material_ids 是当前实际候选目录；空目录时档案取舍札记归入 decision_summary，material_decisions 登记为空。'
                '角色档案挂载逐项保留 known/reference；交接起点登记为 scene_delta.next_handoff。'
                'archive_attachments 的 start_line 与 end_line 同时为空表示全文件，选取行时两端均为整数。'
                '每条委托的 working_context 定位其相关语境段落，未另列时为空；author_prompt 与 style_direction 逐字定位本条邀请及文风。'
                'SceneDelta 的 target_ref 仅从 context.available_delta_targets 选择实际存在且与原文改变对象对应的档案；未来事项进入 next_handoff。')
    if kind == 'material' and context.get('role') == 'character-actor':
        return '一个候选对应完整当轮回应；程序保存 text。整理目标角色本人的言语、动作和私人想法，逐片标注原文位置。'
    if kind == 'material' and context.get('role') == 'event-narrator':
        return ('制度、风俗、世界常识、历史和传言都是本领域文学素材。按原文明示的 confirmed、attributed、proposed'
                '分别登记连续段落，source_note 保留作者给出的来源说明。候选合起来保留完整文学材料。')
    if kind == 'tone':
        return '登记每一处编辑建议的原句、替换句、理由和规则编号。引用锚点落在句子自身，正文见 context.prose。'
    if kind == 'review':
        return 'claim、title、reader_effect 与 direction 登记审读者的判断；evidence 逐字引用 context.prose 的连续片段，优先采用审读原文明确引用的正文。审读者的评语留在判断字段。既有问题沿用 context.review_continuity 中的实际编号。'
    if kind.startswith('planning-'):
        return ('编号、标题、人数、权重与节奏采用直接值。文学任务、阅读经验和各单元策略按原文简要登记；'
                '引用适合需要保留的长段落，短字段直接写出原文中的文字。')
    return '逐项登记原文明示的文学记录。'
