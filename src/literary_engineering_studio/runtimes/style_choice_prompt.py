"""Stable reference contents precede scene-local selection instructions."""
from collections import defaultdict
from copy import deepcopy
import json


def style_choice_prompt(brief, catalog):
    ordered = deepcopy(catalog)
    keys = ('reference_catalog', 'presets', 'base_style')
    ordered = {**{key: ordered[key] for key in keys if key in ordered},
               **{key: value for key, value in ordered.items() if key not in keys}}
    return '\n'.join((
        '先判断这一单元值得让读者经历什么，选择讲述者声音、感知位置、详略和叙述时间。',
        '本次交付文风选择札记：完整阅读参照目录，写出本段文学方式、激活预设 ID、参照 ID 与选择理由。下一轮资料包提供取材委托入口。',
        '参照用于具体的表达功能，原作品的时代口吻和人物称谓无需继承。比较适合本单元的不同来源，'
        '不要因为某部作品样段更多或更长便全部选入；多选应逐项说明独有用途，相近功能可以只选最合适的一段。',
        '先从不同来源比较本段需要的表达功能，选足以支撑任务的最少样段。新目录包括现代叙述、心理距离与日常时间，'
        '不要默认继承两部古典小说的时代语气。引用功能，不移植参照中的人物、年份、数量、风俗或疾病到本作事实。',
        '## 参照来源分布\n' + json.dumps(reference_source_summary(catalog), ensure_ascii=False),
        '## 预设与完整参照目录\n' + json.dumps(ordered, ensure_ascii=False),
        '## 当前单元\n' + json.dumps(brief.to_dict(), ensure_ascii=False)))


def reference_source_summary(catalog):
    grouped = defaultdict(lambda: {'units': 0, 'chars': 0})
    for row in (catalog.get('reference_catalog') or {}).get('references', []):
        source = str(row.get('source_title') or '来源未标明')
        if source.startswith('用户提供样段'):
            source = '用户提供样段（作品身份未核验，不按多个独立作品计数）'
        grouped[source]['units'] += 1
        grouped[source]['chars'] += len(str(row.get('text') or ''))
    return dict(grouped)
