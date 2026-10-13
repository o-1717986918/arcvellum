"""Register only explicit choice words and catalog IDs from the author's notes."""
import re
from .natural_selection_pending import shared_prefix_source,abbreviated_choice_source

WORDS={'use':'use','采用':'use','adapt':'adapt','改写':'adapt','整编':'adapt',
       'discard':'discard','舍下':'discard','舍弃':'discard','defer':'defer','留待':'defer'}


def local_choice_labels(answer,known):
    rows=[];mode=None
    for line,reason in _selection_lines(answer):
        heading=re.match(r'^\*\*([^*]+)\*\*',line.strip())
        label=heading[1] if heading else line
        ids=[identifier for identifier in known if _declared_id(label,identifier,known)]
        if heading and not ids:
            mode=_choice(label);continue
        if not heading and not re.match(r'^\s*[-*]\s+',line):
            continue
        decision=_whole_candidate_choice(label, mode)
        if not decision:
            continue
        for identifier in ids:
            rows.append({'candidate_id':identifier,'decision':decision,'reason':reason.strip(),
                         'source_choice_label':line.strip(),'choice_recovery':'explicit-author-notes-v1'})
    return rows


def _selection_lines(answer):
    lines=answer.splitlines();level=None;active=False
    for index,line in enumerate(lines):
        header=re.match(r'^(#{1,6})\s+',line)
        if re.search(r'(?:取舍札记|素材取舍|取舍登记)',line):
            active=True;level=len(header[1]) if header else None
        elif header and (level is None or len(header[1])<=level or re.search('editor_focus|交接|创作札记',line)):
            active=False
        if not active:
            continue
        yield line,_header_reason(lines,index) if line.startswith('**') else line


def _header_reason(lines,index):
    end=index+1
    while end<len(lines) and not re.match(r'^#{1,6}\s+|^\*\*|^---\s*$',lines[end]):
        end+=1
    return '\n'.join(lines[index:end]).strip()


def _whole_candidate_choice(line, mode):
    if '状态不变' in line:
        return None
    primary = line.split('。', 1)[0]
    decision = _choice(primary) or mode
    if decision == 'discard' and re.search(r'`\s*中|片段|台词|其中', line):
        return None
    return decision


def _choice(line):
    declared=re.findall(r'(?<![A-Za-z])(?:use|adapt|discard|defer)(?![A-Za-z])',line)
    if declared:
        kinds=set(declared)
        if kinds.issubset({'use','adapt'}):
            return 'adapt' if 'adapt' in kinds else 'use'
        return declared[0] if len(kinds)==1 else None
    label=re.match(r'^\s*(?:[-*]\s*)?\*{0,2}(采用(?:/整编)?|改写|整编|舍下|舍弃|留待)',line)
    if not label:
        return None
    return 'adapt' if label[1]=='采用/整编' else WORDS[label[1]]


def _declared_id(line,identifier,known):
    return bool(re.search(re.escape(identifier)+r'(?!\d)',line)
        or shared_prefix_source(line,identifier) or abbreviated_choice_source(line,identifier,known))
