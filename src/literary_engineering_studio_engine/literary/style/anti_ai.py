"""Detect and describe common AI-ish prose habits in generated fiction."""

from __future__ import annotations

from dataclasses import dataclass
import re

from literary_engineering_studio_engine.literary.review.creative_quality import apply_rule_mode, quality_rule_mode, quality_threshold
from .anti_ai_similarity import simile_dependency_finding


ANTI_EVASION_REVISION_PROTOCOL = """## 修订反规避协议

修订不是把一种 AI 腔换成另一种 AI 腔。ArcVellum Worker 处理 review notes、Style Lint 或人工批注时，必须按以下程序执行：

1. 先摘出原句、风险类型和它原本想承担的叙事功能：信息反转、人物误判、因果揭示、视角校正、讽刺顿挫或行动后果。
2. 默认从“不合理”开始挑刺。不要轻易把转折解释为合理修辞；“增强节奏”“体现复杂心理”“更有文学感”不是充分理由。
3. 禁止同功能换皮：不得把“不是……而是……”改成“并不是……只是……”“倒不是……只是……”“看似……其实……”“表面上……实则……”“没有……只是……”“也不……也不……只是……”等同构转折。
4. 能用动作、事实顺序、信息差、直接陈述或人物选择表达的，优先不用显式转折。
5. 若保留显式转折，必须在修订报告中给出负担证明：为什么必须保留、为什么更朴素写法不够、是否仍有换皮嫌疑、最终是否建议继续修订。
6. 修订报告必须列出“原句 / 原问题 / 修订句 / 是否仍含转折 / 是否换皮 / 保留理由 / 批判性反驳 / 结论”。解释不充分时，结论必须是需要再修。
"""

ANTI_EVASION_SHORT_RULE = (
    "修订反规避：不得用“并不是……只是……”“看似……其实……”“表面上……实则……”等同功能转折替换"
    "“不是……而是……”。保留转折需要负担证明，并默认从不合理开始挑刺。"
)

ANTI_AI_STYLE_PROMPT = """## 降低 AI 腔与语言准确性约束

- 生硬对照句式一律禁用：不使用“不是……而是……”“不再是……而是……”“没有再……而是……”“并非……而是……”“与其说……不如说……”“不是……不是……而是……”，也不使用“不是……——是……”“不是……。是……”“不是……，是……”等用标点替代“而是”的变体。此类结构不判断为合理修辞；请改为动作、事实顺序、信息差或直接陈述。
- 禁止换皮转折：不使用“并不是……只是……”“倒不是……只是……”“不是说……只是……”“看似……其实……”“表面上……实则……”“没有……只是……”“也不……也不……只是……”等同功能替代。修订时若保留任何显式转折，必须给出负担证明，并默认从“不合理”开始挑刺。
- 清晰不等于全程平直，白描也不是唯一合法写法。冲突与认识变化处允许语言升起，随行动后果回落；反讽、借代、通感、自由间接引语等手法从人物经验里生长，不用随机碎句代替节奏。
- 器官轮岗、AI 高频套话、万能占位和比喻依赖按现有约 2% 密度规则复核。不要轮流写嘴角、眼底、指尖等部位来代替情绪，也少用“有什么东西……”“仿佛有一只无形的手”等空泛表达；让选择、停顿、话语和细节承担感受。
- 破折号不能制造文学感。正式正文原则上不用“——”做转折、插入或强调；孤立出现需逐句语义复核，超过 2% 密度或替代转折时必须修订。
- 逗号服务句内关系，不按数量机械拆句；句长随本场压力与注意力变化，短句留给真实落点。
- 执行“证据之后停笔”：动作、物证、意象、对白或沉默已经传达含义时，不在段尾、场尾追加翻译潜台词、概括人物感受、宣布主题或解释“这意味着什么”的句子。让后果留在读者能感到的位置，不用无意义解释替读者下结论。
- 景物不必与人物情绪同步。避免没有变化的同义复述；同一感受可以随互动回返、加深或变形。
- 无关精确数字默认不用；“一个又一个”等虚指反复，以及问答、辨认、选择、因果、连续性或后文核验中有用的数值应保留。题材和参考语料不自动授权装饰性读数；逐项判断，不批量删数字或机械模糊化。
- 禁止用正则或批量脚本对正文做语义级“去 AI 腔”改写。脚本只能提示风险或做安全排版规范化；删除“不是”、改写“不是 A——是 B”、替换心理判断等操作必须由 ArcVellum Worker 逐句语义复核。"""

ANTI_AI_STYLE_SHORT_RULE = (
    "降低 AI 腔：禁用“不是……而是……”“不再是……而是……”“没有再……而是……”及“不是……——是”等生硬对照，不判断为合理修辞；"
    "禁用“并不是……只是……”“看似……其实……”等换皮转折；"
    "破折号、器官轮岗、万能占位、比喻依赖和景物强制同步按 2% 左右密度门禁控制；无关精确数字默认不用，虚指反复与当场有用的问答数值不误删，技术、倒计时、场景合同和参考语料不豁免装饰性读数，普通陈设与日常动作不为显得具体而计件、计次或计秒。"
    "按场景压力调整句法、修辞和语域，关键转折应有语言起伏；动作、意象或对白已经传意时停止，不补解释性尾句；不得用脚本批量删除否定或做语义改写。"
)

AI_STYLE_SOFT_DENSITY_LIMIT = 0.02
AI_STYLE_GATE_BLOCKING_RULES = {"mechanical-contrast-frame", "contrast-evasion-frame"}

BANNED_AI_PHRASES: tuple[str, ...] = (
    "嘴角划过弧度",
    "嘴角一扯",
    "勾起嘴角",
    "嘴角微扬",
    "嘴角泛起",
    "笑意不达眼底",
    "眸色一沉",
    "眸中闪过",
    "瞳孔骤缩",
    "眼底有什么东西翻涌",
    "眼底一闪而过",
    "眼眶泛红",
    "眼圈微红",
    "睫毛颤了颤",
    "眉心微蹙",
    "眉头紧锁",
    "下颌线绷紧",
    "喉结滚动",
    "咬着下唇",
    "后槽牙咬得咯吱响",
    "嘴唇翕动",
    "鼻尖发酸",
    "额角青筋隐现",
    "太阳穴突突地跳",
    "指甲陷入肉里",
    "指节发白",
    "指节捏得发白",
    "攥紧拳头",
    "拳头攥了又松",
    "手心全是汗",
    "掌心掐出月牙形的印子",
    "手指收紧",
    "指尖发凉",
    "指尖微微发颤",
    "呼吸一滞",
    "呼吸停了一拍",
    "心脏漏跳一拍",
    "心脏像被攥住",
    "血液凝固",
    "血液往头顶涌",
    "浑身僵硬",
    "僵在原地",
    "脊背发凉",
    "脊背窜上一股寒意",
    "松了一口气",
    "悬着的心落了地",
    "绷紧的弦松了",
    "胸口发闷",
    "喉咙发紧",
    "喉咙发堵",
    "视线模糊",
    "眼前蒙了一层雾",
    "深吸一口气",
    "吐出一口浊气",
    "胃里翻江倒海",
    "胃部一紧",
    "冷得像腊月的冰",
    "冷得像腊月的枯井",
    "眼神冷得像淬了冰",
    "像冰面裂开了一道缝",
    "话像冰碴子一样",
    "溅起水花",
    "暗流涌动",
    "有什么东西在翻涌",
    "悲伤溢出",
    "笑意溢出",
    "漫上心头",
    "酸涩漫上来",
    "有什么东西碎了",
    "泛起涟漪",
    "心湖被搅动",
    "有什么东西",
    "某种说不清的东西",
    "谁也说不清",
    "好像被什么东西攫住了",
    "仿佛有一只无形的手",
    "像溺水的人抓住浮木",
    "像被人掐住了喉咙",
    "像被什么东西击中了",
    "仿佛下一瞬就会碎掉",
    "像绷到极限的弦",
    "像站在悬崖边上",
    "仿佛风一吹就会散",
    "如同潮水般涌来",
    "连他自己都没察觉",
    "连他自己都没意识到",
    "一时之间",
    "不知为何",
    "不知过了多久",
    "说不清是",
    "不知道是",
    "分不清是",
    "几乎就要",
    "差一点就",
    "险些",
    "那是一种",
    "一滞",
    "一顿",
    "一僵",
    "一怔",
    "一愣",
    "一凛",
    "后来他才明白",
    "很久以后他才知道",
    "多年后他依然记得",
)

BANNED_INTENT_TERMS: tuple[str, ...] = (
    "笑意",
    "怒意",
    "寒意",
    "暖意",
    "醉意",
    "倦意",
    "悔意",
    "恨意",
    "杀意",
)


@dataclass(frozen=True)
class AIStyleIssue:
    rule: str
    severity: str
    message: str
    sample: str = ""


def style_lint_gate(text: str, profile: dict[str, object] | None = None, *, scope: str = "") -> dict[str, object]:
    """Return a machine gate result for AI-style lint findings.

    Mechanical contrast frames are always blocking. Other medium-or-higher
    findings are blocking; low findings remain review notes.
    """

    issues = lint_ai_style(text, profile=profile, scope=scope)
    blocking = [issue for issue in issues if is_style_lint_blocking(issue, profile=profile, scope=scope)]
    notes = [issue for issue in issues if not is_style_lint_blocking(issue, profile=profile, scope=scope)]
    status = "blocking" if blocking else ("notes" if notes else "pass")
    return {
        "status": status,
        "blocking_count": len(blocking),
        "note_count": len(notes),
        "blocking": [ai_style_issue_to_dict(issue) for issue in blocking],
        "notes": [ai_style_issue_to_dict(issue) for issue in notes],
    }


def is_style_lint_blocking(issue: AIStyleIssue, profile: dict[str, object] | None = None, *, scope: str = "") -> bool:
    if profile is not None:
        mode = quality_rule_mode(profile, issue.rule, "blocking" if issue.rule in AI_STYLE_GATE_BLOCKING_RULES else "note", scope=scope)
        if mode == "off" or mode == "note":
            return False
        if mode == "blocking":
            return True
    severity = issue.severity.strip().lower()
    return issue.rule in AI_STYLE_GATE_BLOCKING_RULES or severity not in {"", "low"}


def ai_style_issue_to_dict(issue: AIStyleIssue) -> dict[str, str]:
    return {
        "rule": issue.rule,
        "severity": issue.severity,
        "message": issue.message,
        "sample": issue.sample,
    }


def style_lint_gate_message(gate: dict[str, object], *, max_items: int = 3) -> str:
    blocking = gate.get("blocking")
    notes = gate.get("notes")
    items = blocking if isinstance(blocking, list) and blocking else notes if isinstance(notes, list) else []
    if not items:
        return "Style Lint clean"
    rendered = []
    for item in items[:max_items]:
        if not isinstance(item, dict):
            continue
        sample = str(item.get("sample") or "").strip()
        suffix = f" 示例：{sample}" if sample else ""
        rendered.append(f"{item.get('rule', 'unknown')}[{item.get('severity', '')}]{suffix}")
    extra_count = max(0, len(items) - len(rendered))
    if extra_count:
        rendered.append(f"另有 {extra_count} 项")
    return "；".join(rendered) if rendered else "Style Lint findings present"


def render_ai_style_lint_block(
    text: str,
    *,
    profile: dict[str, object] | None = None,
    scope: str = "",
    max_issues: int = 12,
    max_sample_chars: int = 120,
) -> str:
    """Render deterministic AI-style lint evidence for Worker review prompts."""

    issues = lint_ai_style(text, profile=profile, scope=scope)
    lines = [
        "## Style Lint (auto-detected)",
        "",
        f"规则摘要：{ANTI_AI_STYLE_SHORT_RULE}",
        "",
        "本区块由确定性代码在审查前生成，是审查证据，不是自动改稿指令。"
        "中级及以上风险必须进入 blocking_issues、warnings 或 revision_actions；"
        "低级风险至少需要语义复核。不得把“不是 A——是 B”等变体判断为合理修辞，"
        "也不得用“看似 A，其实 B”等换皮转折替代；不得用脚本直接删改正文造成语义反转。",
        "",
    ]
    if not text.strip():
        lines.append("- [medium] draft-missing: 未读取到可审查正文，必须先补齐 draft 后再做正式审查。")
        return "\n".join(lines).rstrip() + "\n"
    if not issues:
        lines.append("- 未检出确定性 AI 腔 / 生硬对照 / 标点节奏风险；仍需 ArcVellum Worker 做语义审查。")
        return "\n".join(lines).rstrip() + "\n"
    for issue in issues[:max_issues]:
        lines.append(f"- [{issue.severity}] {issue.rule}: {issue.message}")
        if issue.sample:
            lines.append(f"  样本：`{_sanitize_sample(issue.sample, max_sample_chars)}`")
    if len(issues) > max_issues:
        lines.append(f"- 另有 {len(issues) - max_issues} 项未展开；审查时需回到 draft 全文复核。")
    return "\n".join(lines).rstrip() + "\n"


def lint_ai_style(text: str, profile: dict[str, object] | None = None, *, scope: str = "") -> list[AIStyleIssue]:
    clean = _strip_markdown(text)
    issues: list[AIStyleIssue] = []
    issues.extend(_banned_phrase_issues(clean, profile))
    contrast_issues = _contrast_frame_issues(clean)
    issues.extend(contrast_issues)
    evasion_issues = _contrast_evasion_issues(clean)
    issues.extend(evasion_issues)
    issues.extend(_sentence_shape_issues(clean, profile=profile, skip_dash=bool(contrast_issues or evasion_issues)))
    issues.extend(_abstract_summary_issues(clean, profile))
    issues.extend(_explanatory_mind_issues(clean))
    issues.extend(_slogan_ending_issues(clean))
    return _apply_profile_modes(issues, profile, scope=scope)


def _banned_phrase_issues(text: str, profile: dict[str, object] | None = None) -> list[AIStyleIssue]:
    custom_phrases = profile.get("custom_banned_phrases") if isinstance(profile, dict) else []
    custom_phrases = custom_phrases if isinstance(custom_phrases, list) else []
    hits = _phrase_hits(text, custom_phrases)
    if not hits:
        return []
    sample = _first_present_sample(text, [hit for hit in hits if not hit.startswith("X意泛滥")] or [hits[0]])
    severity, density_note = _soft_density_verdict(len(hits), text, profile)
    rule = "custom-banned-phrase" if any(str(item) in sample for item in custom_phrases or []) else "plain-narration-banned-expression"
    return [AIStyleIssue(
            rule, severity,
            "出现空泛或模板化的风险词句，容易显得像 AI 在演小说。"
            f"此类词组按约 2% 密度门禁处理，{density_note}；请按当前人物视角和场景语势，改为准确的动作、事实或感知。",
            sample or hits[0],
        )]
def _phrase_hits(text: str, custom_phrases: list[object]) -> list[str]:
    hits = [phrase for phrase in BANNED_AI_PHRASES for _ in range(text.count(phrase))]
    hits.extend(str(phrase) for phrase in custom_phrases for _ in range(text.count(str(phrase))) if str(phrase))
    intent_hits = [term for term in BANNED_INTENT_TERMS for _ in range(text.count(term))]
    if len(intent_hits) >= 3:
        hits.append("X意泛滥：" + "、".join(sorted(set(intent_hits))[:5]))
    return hits
def _contrast_frame_issues(text: str) -> list[AIStyleIssue]:
    patterns = [
        r"不是[^。！？!?；;\n]{1,50}?而是",
        r"不再是[^。！？!?；;\n]{1,50}?而是",
        r"没有再[^。！？!?；;\n]{1,50}?而是",
        r"不是[^。！？!?；;\n]{1,50}?——\s*是",
        r"不是[^。！？!?；;\n]{1,50}?[，,]\s*是",
        r"不是[^。！？!?；;\n]{1,50}?。\s*是",
        r"不是[^。！？!?；;\n]{1,50}?[。！？!?][”’]?(?:[^，。！？!?\n]{0,16}?(?:说|问|答|道|解释|回应))[，,:：][“‘]?\s*是",
        r"并非[^。！？!?；;\n]{1,50}?而是",
        r"并非[^。！？!?；;\n]{1,50}?——\s*是",
        r"与其说[^。！？!?；;\n]{1,40}?不如说",
    ]
    hits: list[str] = []
    for pattern in patterns:
        hits.extend(match.group(0) for match in re.finditer(pattern, text))
    hits = list(dict.fromkeys(hits))
    if not hits:
        return []
    return [
        AIStyleIssue(
            "mechanical-contrast-frame",
            "medium",
            "发现生硬对照句式。此类“不是……而是……”“不再是……而是……”“没有再……而是……”及其破折号/句号变体不判断为合理修辞；请改为动作、事实顺序、信息差或直接陈述。不得用脚本直接删除否定词导致语义反转。",
            _sample(text, hits[0]),
        )
    ]


def _contrast_evasion_issues(text: str) -> list[AIStyleIssue]:
    patterns = [
        r"(?:并不是|倒不是|不是说)[^。！？!?；;\n]{1,50}?(?:只是|只不过)",
        r"(?:看似|看起来|表面上)[^。！？!?；;\n]{1,50}?(?:其实|实则|实际上)",
        r"没有[^。！？!?；;\n]{1,40}?(?:只是|只不过|不过是)",
        r"也不[^。！？!?；;\n]{1,18}?[，,]也不[^。！？!?；;\n]{1,18}?[，,]只是",
    ]
    hits: list[str] = []
    for pattern in patterns:
        hits.extend(match.group(0) for match in re.finditer(pattern, text))
    hits = list(dict.fromkeys(hits))
    if not hits:
        return []
    return [
        AIStyleIssue(
            "contrast-evasion-frame",
            "medium",
            "发现疑似换皮转折。不要把“不是……而是……”改写成“并不是……只是……”“看似……其实……”等同功能结构；若保留显式转折，必须给出负担证明，并优先尝试动作、事实顺序、信息差或直接陈述。",
            _sample(text, hits[0]),
        )
    ]


def _sentence_shape_issues(
    text: str,
    *,
    profile: dict[str, object] | None = None,
    skip_dash: bool = False,
) -> list[AIStyleIssue]:
    issues: list[AIStyleIssue] = []
    max_comma_overload_issues = 8
    dash_count = text.count("——")
    if dash_count and not skip_dash:
        severity, density_note = _soft_density_verdict(
            dash_count,
            text,
            profile,
            threshold_key="dash_per_100_units",
        )
        issues.append(
            AIStyleIssue(
                "dash-prohibited-in-plain-narration",
                severity,
                "当前中文标点约束原则上不用破折号。不要用破折号制造文学感、插入感或转折感；"
                f"{density_note}。请改为换句、换段或删去多余渲染。",
                _sample(text, "——"),
            )
        )
    comma_overload_count = 0
    for sentence in re.split(r"[。！？!?\n]", text):
        comma_limit = int(quality_threshold(profile, "commas_per_sentence", 3))
        comma_count = sentence.count("，") + sentence.count(",")
        sentence_cjk = len(re.findall(r"[\u3400-\u4dbf\u4e00-\u9fff]", sentence))
        min_chars = int(quality_threshold(profile, "comma_overload_min_chars", 56))
        if comma_count > comma_limit and (
            sentence_cjk >= min_chars or comma_count > comma_limit + 2
        ):
            issues.append(
                AIStyleIssue(
                    "comma-overload-in-sentence",
                    "medium",
                    f"较长句包含超过 {comma_limit} 个逗号，句内层级可能松散。请先重组动作、观察或因果层级；只有语义已经结束时才断句，不要机械拆成同构短句。",
                    sentence.strip()[:100],
                )
            )
            comma_overload_count += 1
            if comma_overload_count >= max_comma_overload_issues:
                break
    transition_patterns = [
        r"也不[^，。！？\n]{1,12}[，,]也不[^，。！？\n]{1,12}[，,]只是",
        r"很[^，。！？\n]{1,8}[，,]很[^，。！？\n]{1,8}[，,]但(?:确实|的确)",
        r"(?:到底还是|终究|终于|还是)[^。！？\n]{0,24}",
        r"(?:不知为何|不知过了多久|说不清是|不知道是|分不清是)[^。！？\n]{0,36}",
        r"嘴上没说什么[^。！？\n]{0,18}却",
        r"(?:安静。很安静。|死一般的安静)",
        r"(?:风|雨|灯|夜色)[^。！？\n]{0,12}(?:恰好|正好|忽然|突然)",
        r"(?:恰好|正好|忽然|突然)[^。！？\n]{0,12}(?:风|雨|灯|夜色)",
    ]
    for pattern in transition_patterns:
        match = re.search(pattern, text)
        if match:
            severity, density_note = _soft_density_verdict(1, text, profile)
            issues.append(
                AIStyleIssue(
                    "plain-narration-template-sentence",
                    severity,
                    "发现模板化叙述风险句式。"
                    f"此类模板按约 2% 密度门禁处理，{density_note}；请去掉表演化转折、景物强制同步或重复渲染，改为直接事实和具体动作。",
                    _sample(text, match.group(0)),
                )
            )
            break
    if finding := simile_dependency_finding(text, profile, _soft_density_verdict):
        issues.append(
            AIStyleIssue(
                finding[0], finding[1], finding[2],
                _first_present_sample(text, ["好像", "仿佛", "如同", "像"]),
            )
        )
    return issues


def _abstract_summary_issues(
    text: str,
    profile: dict[str, object] | None = None,
) -> list[AIStyleIssue]:
    patterns = [
        r"某种意义(?:上)?",
        r"某种(?:说不清|难以言说|无法形容|莫名的)[^。！？\n]{0,12}",
        r"一种(?:说不清|难以言说|无法形容|莫名的)[^。！？\n]{0,12}",
        r"(?:答案|真相|命运|存在)本身",
        r"(?:这一刻|此刻)[^。！？\n]{0,20}(?:终于|才|忽然|突然|明白|意识到|知道)",
    ]
    hits = [match.group(0) for pattern in patterns for match in re.finditer(pattern, text)]
    if not hits:
        return []
    severity, density_note = _soft_density_verdict(len(hits), text, profile)
    if severity != "medium":
        return []
    return [
        AIStyleIssue(
            "abstract-summary-density",
            "medium",
            "抽象总结模板密度偏高，可能用概念替代了具体叙事。"
            f"{density_note}；请逐项改为可观察的动作、事实或后果。",
            _first_present_sample(text, hits),
        )
    ]


def _explanatory_mind_issues(text: str) -> list[AIStyleIssue]:
    patterns = [
        r"[他她它](?:知道|明白|意识到|发现|觉得)",
        r"[他她它]突然(?:知道|明白|意识到|发现|觉得)",
        r"[他她它]终于(?:知道|明白|意识到|发现|觉得)",
    ]
    hits: list[str] = []
    for pattern in patterns:
        hits.extend(re.findall(pattern, text))
    if len(hits) < 4:
        return []
    return [
        AIStyleIssue(
            "explanatory-psychology-overuse",
            "medium",
            "解释性心理标签过多；请用选择、动作、停顿、回避和对白潜台词呈现认知变化。",
            _sample(text, hits[0]),
        )
    ]


def _slogan_ending_issues(text: str) -> list[AIStyleIssue]:
    paragraphs = [item.strip() for item in re.split(r"\n\s*\n", text) if item.strip()]
    if not paragraphs:
        return []
    tail = paragraphs[-1]
    if len(tail) > 90:
        return []
    if re.search(r"(这就是|那就是|终于明白|真正的|唯一的|不是.+而是|答案|真相|命运|意义)", tail):
        return [
            AIStyleIssue(
                "slogan-like-ending",
                "low",
                "场景结尾有金句化或主题直说倾向；优先落在动作结果、关系变化、信息揭示或悬念上。",
                tail[:80],
            )
        ]
    return []


def _strip_markdown(text: str) -> str:
    lines = []
    in_fence = False
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if line.startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        if re.match(r"^#{1,6}\s+", line):
            continue
        if line.startswith("- ["):
            continue
        lines.append(raw_line)
    return "\n".join(lines)


def _soft_density_verdict(
    hit_count: int,
    text: str,
    profile: dict[str, object] | None = None,
    *,
    threshold_key: str = "soft_density_per_100_units",
) -> tuple[str, str]:
    unit_count = _narrative_unit_count(text)
    per_100 = quality_threshold(profile, threshold_key, AI_STYLE_SOFT_DENSITY_LIMIT * 100)
    density_limit = per_100 / 100
    allowed = max(1, int(unit_count * density_limit))
    density = hit_count / max(unit_count, 1)
    severity = "medium" if hit_count > allowed else "low"
    return severity, f"当前 {hit_count}/{unit_count} 个叙事单元，约 {density:.1%}，阈值为每 100 个叙事单元 {per_100:g} 次"


def _apply_profile_modes(issues: list[AIStyleIssue], profile: dict[str, object] | None, *, scope: str = "") -> list[AIStyleIssue]:
    if profile is None:
        return issues
    adjusted: list[AIStyleIssue] = []
    for issue in issues:
        default = "blocking" if issue.rule in AI_STYLE_GATE_BLOCKING_RULES else "note"
        severity = apply_rule_mode(issue.severity, quality_rule_mode(profile, issue.rule, default, scope=scope))
        if severity is not None:
            adjusted.append(AIStyleIssue(issue.rule, severity, issue.message, issue.sample))
    return adjusted


def _narrative_unit_count(text: str) -> int:
    units = [unit for unit in re.split(r"[。！？!?；;\n]+", text) if unit.strip()]
    return max(1, len(units))


def _sample(text: str, hit: str) -> str:
    idx = text.find(hit)
    if idx < 0:
        return hit[:80]
    start = max(0, idx - 24)
    end = min(len(text), idx + len(hit) + 36)
    return text[start:end].strip()


def _first_present_sample(text: str, terms: list[str]) -> str:
    positions = [(text.find(term), term) for term in terms if text.find(term) >= 0]
    if not positions:
        return ""
    _, term = min(positions)
    return _sample(text, term)


def _sanitize_sample(value: str, max_chars: int) -> str:
    text = re.sub(r"\s+", " ", value).strip().replace("`", "'")
    if len(text) <= max_chars:
        return text
    return text[: max(0, max_chars - 1)].rstrip() + "..."
