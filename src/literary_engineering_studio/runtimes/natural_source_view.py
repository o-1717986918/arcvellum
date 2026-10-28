"""Compact model-only source labels; Engine IDs and preserved text stay unchanged."""
import json


def model_source_view(index, answer):
    legacy = {
        'source_text': answer,
        'source_index': {'sha256': index['sha256'], 'blocks': [
            [row['id'], row['beginning'], row['ending']] for row in index['blocks']]},
    }
    if len(index['blocks']) < 24:
        return legacy
    parts, cursor = [], 0
    for row in index['blocks']:
        parts.extend((answer[cursor:row['start']], '[' + row['id'] + '] ',
                      answer[row['start']:row['end']]))
        cursor = row['end']
    parts.append(answer[cursor:])
    labelled = {
        'source_text': ''.join(parts),
        'source_index': {
            'sha256': index['sha256'],
            'presentation': 'labelled-lines-v1',
            'block_count': len(index['blocks']),
            'labels': '每个非空行前添加的 [bNNNN] 是定位标签，不属于原文。'
                      'first_block/last_block 使用标签内的原始 ID；锚点只引用该标签后面的原文字句。'
                      '程序按保存原文恢复，禁止把定位标签写入正文。',
        },
    }
    size = lambda value: len(json.dumps(value, ensure_ascii=False, separators=(',', ':')).encode('utf-8'))
    old_size, new_size = size(legacy), size(labelled)
    return labelled if old_size - new_size >= 2048 and new_size <= old_size * .9 else legacy
