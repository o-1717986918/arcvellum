"""Standard Chinese punctuation guardrails and lightweight linting."""

from __future__ import annotations

from dataclasses import dataclass
import re


PUNCTUATION_STANDARD_TITLE = "标准中文标点约束"

PUNCTUATION_STANDARD_PROMPT = """标准中文标点与文学节奏约束：

一、基础排版规则：

- 中文叙事、对白、报告和说明默认使用全角中文标点：，。；：？！、（）《》“”‘’。
- 中文正文中不要混用英文逗号、句号、冒号、分号、问号、感叹号或英文引号；英文缩写、URL、文件路径、代码、schema 字段和小数除外。
- 省略号统一使用“……”，不要使用“...”或连续句点；破折号统一使用“——”，不要用“--”或单个“—”表达停顿。
- 疑问号、感叹号通常只使用一个；避免“！！！”“？？？”“?!”等网感化连续标点，除非用户明确要求实验性文本或角色文本确有格式依据。
- 横排文学正文的直接引语统一使用中文双引号“”；引语内再引语使用中文单引号‘’。不要在不同章节混用「」『』、﹁﹂﹃﹄、｢｣等竖排/角引号，除非项目记录了明确的版式例外。
- 不要在中文标点前留空格，不要连续堆叠逗号、句号、顿号、冒号或分号。

二、文学节奏规则：

- 标点是叙事运动的一部分，不是装饰。先判断句子承载的动作、感知、心理和因果关系，再选择停顿。
- 句号用于完成一个语义落点、镜头落点或心理落点。不要把同一组连续动作切成一串过短句号；若动作仍在同一感知链、因果链或情绪波内，优先用逗号、分号、顿号或重写句法承接。
- 逗号用于未完成的关系：动作延续、视线移动、心理补充、因果递进。不要用逗号串接过多彼此独立的动作；长逗号链应拆为句群，或用分号区分并列层级。
- 破折号只可作为需要复核的强停顿信号。普通正式正文原则上不用破折号；孤立出现时必须确认它承担话语中断、真实插入或必要解释，不是把“但是/而是/于是”换成装饰性停顿。超过约 2% 叙事单元密度、同段反复出现，或构成“不是……——是……”等生硬对照时，必须修订。
- 若文风证据中存在高破折号节奏，只能抽象其停顿、讽刺、信息反转或话语中断功能，不把破折号密集使用写成生成模板；平台 agent 必须逐句判断，不得按正则批量删改。
- 转折不应主要依赖“但是、然而、于是、然后、突然”等显性连接词。优先用人物动作、视线变化、物象回声、信息差和句法重心制造转折；显性转折词只在逻辑关系需要被点明时使用。
- 长短句应围绕注意力变化调度：观察和铺陈可以稍长，判断、发现、拒绝、危险逼近可以短，但短句必须有信息落点，不能只是模型化碎句。
- 对白提示语的标点服务说话动作和语气。不要让提示语反复用同一种“他说。”式句号收束；可通过动作、停顿、沉默和环境反应形成段落节奏。

三、例外区域：

- Markdown、JSON、YAML、代码块、文件路径、命令、URL、模型名和英文术语保留其必要 ASCII 符号，不做机械替换。
- 文风学习可以调整标点节奏和密度，但不能突破以上基础规范；如确需保留非标准标点或极端节奏，必须在审查或“需要人工确认”中说明理由。机械“不是……而是……”及其破折号/句号变体不得被判断为合理修辞。"""

PUNCTUATION_STANDARD_SHORT_RULE = (
    "中文用户可见文本必须遵守标准中文标点约束：中文正文用全角标点，省略号用“……”，"
    "破折号用“——”，直接引语统一用“”且内层引语用‘’，不要章节间混用「」『』等竖排/角引号；"
    "避免英文标点混入中文句子、连续感叹/疑问符和中文标点前空格；"
    "同时控制文学节奏：句号用于真实语义落点，逗号承接未完成关系，正式正文原则上不用破折号，"
    "孤立破折号需逐句复核，超过约 2% 密度或替代“而是/但是/于是”时必须修订；转折优先由动作、意象和因果生成，避免机械堆叠“但是、然而、于是、然后”。"
    "代码、路径、URL、JSON/YAML/schema 字段除外。"
)


@dataclass(frozen=True)
class PunctuationIssue:
    rule: str
    severity: str
    message: str
    sample: str


CHINESE_RANGE = r"\u3400-\u4dbf\u4e00-\u9fff"
CORNER_QUOTE_RE = re.compile(r"[「」『』﹁﹂﹃﹄｢｣]")
QUOTE_NORMALIZATION_MAP = str.maketrans(
    {
        "「": "“",
        "」": "”",
        "﹁": "“",
        "﹂": "”",
        "｢": "“",
        "｣": "”",
        "『": "‘",
        "』": "’",
        "﹃": "‘",
        "﹄": "’",
    }
)


def lint_punctuation(text: str) -> list[PunctuationIssue]:
    """Return punctuation issues for Chinese prose-like text.

    This linter is intentionally conservative and skips fenced code blocks so
    Markdown contracts, JSON examples, paths, and commands are not normalized by
    accident. It is a gate for prose quality, not a full typography engine.
    """

    clean = _strip_fenced_code(text)
    checks: list[tuple[str, str, str, re.Pattern[str]]] = [
        (
            "ascii-punctuation-in-chinese",
            "medium",
            "中文句子中混入英文标点，应改为全角中文标点，除非是路径、URL、代码或英文术语。",
            re.compile(rf"(?<=[{CHINESE_RANGE}])[,.!?;:]|[,.!?;:](?=[{CHINESE_RANGE}])"),
        ),
        (
            "ascii-ellipsis",
            "medium",
            "省略号应使用“……”，不要使用“...”或连续英文句点。",
            re.compile(r"\.\.\.+"),
        ),
        (
            "ascii-dash",
            "low",
            "中文停顿破折号应使用“——”，不要使用“--”或单个“—”。",
            re.compile(rf"(?<=[{CHINESE_RANGE}])--(?=[{CHINESE_RANGE}])|(?<!—)—(?!—)"),
        ),
        (
            "western-quotes-in-chinese",
            "low",
            "中文引语应优先使用“”或‘’，不要在中文正文中混用英文直引号。",
            re.compile(rf"(?<=[{CHINESE_RANGE}])[\"']|[\"'](?=[{CHINESE_RANGE}])"),
        ),
        (
            "corner-quotes-in-horizontal-prose",
            "medium",
            "横排文学正文直接引语应统一使用“”和内层‘’，不要章节间混用「」『』、﹁﹂﹃﹄或｢｣等竖排/角引号。",
            CORNER_QUOTE_RE,
        ),
        (
            "punctuation-spacing",
            "low",
            "中文标点前不应留空格。",
            re.compile(r"[ \t]+[，。！？；：、）】》”’]"),
        ),
        (
            "repeated-terminal-punctuation",
            "medium",
            "避免连续堆叠疑问号、感叹号或中英混合疑问/感叹标点。",
            re.compile(r"[!?！？]{2,}"),
        ),
        (
            "repeated-punctuation",
            "medium",
            "避免连续堆叠逗号、句号、顿号、冒号或分号。",
            re.compile(r"[，。；：、]{2,}"),
        ),
    ]
    issues: list[PunctuationIssue] = []
    for rule, severity, message, pattern in checks:
        match = pattern.search(clean)
        if match:
            issues.append(PunctuationIssue(rule, severity, message, _sample(clean, match.start(), match.end())))
    issues.extend(_lint_literary_punctuation_rhythm(clean))
    return issues


def render_punctuation_standard_for_prompt() -> str:
    return PUNCTUATION_STANDARD_PROMPT


def normalize_punctuation_for_delivery(text: str) -> str:
    """Normalize safe delivery-level punctuation variants.

    This intentionally limits itself to quote-style unification so final
    exports do not silently rewrite literary rhythm or code-like content.
    """

    return text.translate(QUOTE_NORMALIZATION_MAP)


def _lint_literary_punctuation_rhythm(text: str) -> list[PunctuationIssue]:
    issues: list[PunctuationIssue] = []
    prose = _strip_markdown_scaffolding(text)
    cjk_count = len(re.findall(rf"[{CHINESE_RANGE}]", prose))
    if cjk_count < 80:
        return issues

    terminal_count = len(re.findall(r"[。！？]", prose))
    period_count = prose.count("。")
    if terminal_count >= 8 and period_count / max(terminal_count, 1) >= 0.85:
        chars_per_terminal = cjk_count / max(terminal_count, 1)
        if chars_per_terminal < 14:
            issues.append(
                PunctuationIssue(
                    "staccato-period-overuse",
                    "medium",
                    "句号密度过高，短句切分过碎。请检查是否把同一组动作、感知或心理波动机械拆成多个句号；同一语义链可改用逗号、分号或重写句群。",
                    _first_paragraph_sample(prose),
                )
            )

    for sentence in _terminal_units(prose):
        comma_count = len(re.findall(r"[，、；]", sentence))
        sentence_cjk = len(re.findall(rf"[{CHINESE_RANGE}]", sentence))
        if sentence_cjk >= 70 and comma_count >= 5:
            issues.append(
                PunctuationIssue(
                    "comma-chain-overload",
                    "medium",
                    "逗号链过长，句内关系可能被机械串接。请拆出清晰句群，或用分号区分并列层级，让动作、心理和因果关系更明确。",
                    sentence.strip()[:90],
                )
            )
            break

    dash_count = prose.count("——")
    if dash_count >= 4 or any(paragraph.count("——") >= 3 for paragraph in prose.splitlines() if paragraph.strip()):
        issues.append(
                PunctuationIssue(
                    "dash-overuse",
                    "medium",
                    "破折号使用过密。普通正式正文原则上不用破折号；超过约 2% 密度、同段反复出现，或替代“而是/但是/于是”时必须修订。请改用句法、逗号、分号、换句或动作承接；不得用脚本批量删除导致语义反转。",
                    _first_dash_sample(prose),
                )
            )

    transition_matches = list(
        re.finditer(r"(?:^|[。！？\n])\s*(但是|可是|然而|不过|于是|所以|因此|然后|接着|突然|与此同时|另一方面)[，,]", prose)
    )
    inline_transition_matches = list(re.finditer(r"[，,](但是|可是|然而|不过|于是|所以|因此|然后|接着|突然)[，,]", prose))
    if len(transition_matches) + len(inline_transition_matches) >= 4:
        match = (transition_matches + inline_transition_matches)[0]
        issues.append(
            PunctuationIssue(
                "mechanical-transition-overuse",
                "medium",
                "显性转折词使用过密，转折可能显得生硬。优先用人物动作、视线变化、物象回声、信息差和因果推进制造转折，只在逻辑必须点明时使用“但是、然而、于是”等连接词。",
                _sample(prose, match.start(), match.end()),
            )
        )

    return issues


def _terminal_units(text: str) -> list[str]:
    return [unit for unit in re.split(r"[。！？]", text) if unit.strip()]


def _strip_markdown_scaffolding(text: str) -> str:
    lines = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            lines.append("")
            continue
        if stripped.startswith(("#", "|", "- [", "- `")):
            continue
        lines.append(line)
    return "\n".join(lines)


def _first_paragraph_sample(text: str) -> str:
    for paragraph in text.splitlines():
        stripped = paragraph.strip()
        if stripped:
            return stripped[:120]
    return ""


def _first_dash_sample(text: str) -> str:
    index = text.find("——")
    return _sample(text, index, index + 2) if index >= 0 else _first_paragraph_sample(text)


def _strip_fenced_code(text: str) -> str:
    return re.sub(r"```.*?```", "", text, flags=re.S)


def _sample(text: str, start: int, end: int, radius: int = 24) -> str:
    left = max(0, start - radius)
    right = min(len(text), end + radius)
    sample = text[left:right].replace("\n", " ").strip()
    if left:
        sample = "..." + sample
    if right < len(text):
        sample += "..."
    return sample
