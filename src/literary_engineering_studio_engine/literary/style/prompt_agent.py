"""Agent-backed LLM-facing style prompt generation."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from literary_engineering_studio_engine.prompting.agents.provider import run_agent_task
from literary_engineering_studio_engine.prompting.agents.schema import validate_agent_run
from literary_engineering_studio_engine.literary.style.prompt import STYLE_PROMPT_LENGTH_RULE, STYLE_PROMPT_QUALITY_RULE


@dataclass(frozen=True)
class AgentStylePromptResult:
    profile_dir: Path
    run_dir: Path
    output_path: Path
    json_path: Path
    validation_path: Path
    provider: str
    generated_chars: int


def build_agent_style_prompt(
    profile_dir: Path,
    *,
    provider: str = "auto",
    output: Path | None = None,
    json_output: Path | None = None,
) -> AgentStylePromptResult:
    profile_root = profile_dir.resolve()
    if not profile_root.is_dir():
        raise FileNotFoundError(f"profile dir not found: {profile_root}")
    profile_path = profile_root / "style-profile.md"
    metrics_path = profile_root / "style_metrics.json"
    manifest_path = profile_root / "corpus_manifest.yaml"
    if not profile_path.exists():
        raise FileNotFoundError(f"style profile not found: {profile_path}")
    if not metrics_path.exists():
        raise FileNotFoundError(f"style metrics not found: {metrics_path}")
    source_paths = [str(profile_path), str(metrics_path)]
    if manifest_path.exists():
        source_paths.append(str(manifest_path))
    dry_payload = _dry_style_prompt(source_paths)
    run_result = run_agent_task(
        profile_root,
        agent_id="style-prompt-builder",
        task="build-llm-facing-style-prompt",
        system_prompt=_system_prompt(),
        user_prompt=_user_prompt(profile_path, metrics_path, manifest_path),
        provider=provider,
        output_dir=profile_root / "agent_runs" / f"style_prompt_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        metadata={"schema_name": "style_prompt.v1", "source_paths": source_paths},
        dry_run_output=dry_payload,
    )
    validation = validate_agent_run(profile_root, run_dir=run_result.run_dir, schema_name="style_prompt.v1")
    parsed = json.loads(run_result.parsed_output_path.read_text(encoding="utf-8"))
    prompt_markdown = str(parsed.get("prompt_markdown", "")).strip()
    output_path = _resolve_output(profile_root, output, "style_prompt.md")
    json_path = _resolve_output(profile_root, json_output, "style_prompt.agent.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(prompt_markdown + "\n", encoding="utf-8")
    parsed["agent_run_dir"] = str(run_result.run_dir)
    parsed["schema_validation"] = str(validation.validation_path)
    parsed["output"] = str(output_path)
    json_path.write_text(json.dumps(parsed, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return AgentStylePromptResult(
        profile_dir=profile_root,
        run_dir=run_result.run_dir,
        output_path=output_path,
        json_path=json_path,
        validation_path=validation.validation_path,
        provider=provider,
        generated_chars=len(prompt_markdown),
    )


def _system_prompt() -> str:
    return f"""You are a literary style prompt engineering agent.

Convert style profile evidence into an LLM-facing style constraint prompt. The output must be JSON using style_prompt.v1, and `prompt_markdown` must be directly usable as a generation prompt. {STYLE_PROMPT_LENGTH_RULE} {STYLE_PROMPT_QUALITY_RULE} Use a core-ban plus density-gate model: mechanical contrast frames are not reasonable rhetoric and must not be authorized as reusable sentence templates; extract their narrative function instead. Cliche phrase families, organ-rotation, generic placeholders, simile dependency, and dash-heavy cadence are soft-density risks with an approximately 2% narrative-unit threshold. Treat exact quantities separately: repeated indefinite expressions such as “one after another” are not exact counts; a precise value may be kept when it materially answers an in-scene question, supports negotiation or identification, changes a choice, preserves causality or continuity, or is verified later. These are alternative functions, not five mandatory simultaneous tests. Incidental measurements and gesture/object counts remain disfavored even in technical scenes, countdowns, scene contracts, and reference excerpts. Preserve established facts accurately; never turn this into a digit count, regex, or numeric-density gate. Distinguish each character's diction, sentence shape, and evasions from known identity and relationship pressure without inventing dialect or catchphrases."""


def _user_prompt(profile_path: Path, metrics_path: Path, manifest_path: Path) -> str:
    manifest = manifest_path.read_text(encoding="utf-8") if manifest_path.exists() else "missing"
    return f"""## style-profile.md

```markdown
{profile_path.read_text(encoding="utf-8")[:9000]}
```

## style_metrics.json

```json
{metrics_path.read_text(encoding="utf-8")[:6000]}
```

## corpus_manifest.yaml

```yaml
{manifest[:4000]}
```
"""


def _dry_style_prompt(source_paths: list[str]) -> dict[str, object]:
    prompt = """# LLM 文风约束提示词

## 使用身份

你是长篇虚构文本生成 LLM。你必须把风格 profile 转化为叙述距离、句法节奏、意象调度、心理呈现和对白动作的稳定约束。本提示词是可挂载文风文件，要求足够详细但不臃肿，正文应维持在 500-2500 中文内容字符之间，计入汉字和中文标点，不计入 Markdown 标记、英文路径、代码围栏或空白；不得用一句“像某作家”替代可执行规则，也不得把统计报告原样塞给生成模型。

## 适用边界与优先级

本文风只决定表达层：叙述距离、句法节奏、意象系统、心理呈现、对白密度和段落推进。它不能覆盖 canon、人物事实、剧情因果、安全边界和用户明确要求。若文风与硬事实冲突，保留硬事实，并把冲突写入需要人工确认。

## 核心约束

- 优先模仿叙事机制，不机械复用原文词句。每场从完整参考语料中选一篇主参照，提取叙述距离、句群呼吸、细节顺序、修辞发动、对白回弹或意象推进中的至少两项，并在初稿中实际使用；不能只借题材词或概括成抽象风格词。
- 句法节奏应跟随人物注意力和场景压力变化。紧张处可以缩短句子，但不能用连续短句伪造节奏；舒缓处可以延展句群。白描只是可用底色之一，承压处可选自由间接引语、反讽、借代、通感、复沓、意象回返或长句推进，让修辞参与认识和关系变化。
- 意象应从场景物理空间和人物处境中生长。重复意象必须带来关系、压力或认知的变化。允许细节积蓄气氛、显露趣味或延长审美时间，不要求每段都即时推进外部事件。
- 心理描写优先通过迟疑、回避、误判、沉默、动作折返和对白遮掩呈现。背景故事只能作为隐性行为因果，不得直白解释。
- 所有风格选择都必须服从 canon、人物 BDI、场景目标和人工确认边界。文风只能决定表达层，不能新增事实、改写关系或替剧情解决问题。

## 标点和段落

中文正文使用标准全角标点，省略号用“……”。句号用于真实落点；逗号用于未完成关系；分号用于层级并列；正式正文原则上不用破折号，孤立破折号需逐句语义复核，超过约 2% 叙事单元密度或替代“而是/但是/于是”时必须修订。若 profile 证据中存在高破折号节奏，只抽象其停顿、讽刺、信息反转或话语中断功能，不把破折号密集使用写成生成模板。转折优先由动作、视线、意象、信息差和因果推进完成，少用机械连接词。

## 对白与动作

对白应带有关系压力和信息差，避免把设定直接说出口。动作不是填充物，应体现人物目标、恐惧、道德边界或隐藏背景留下的选择惯性；气氛段落可以暂缓事件，却要改变读者的感受时间。
从人物已有背景、身份、欲望和关系压力区分词域、句形、礼貌边界、幽默方式与回避策略；人物可以随场面变化说法，但不能都说成同一种平直语气，也不凭空添加方言或口头禅。

## 降低 AI 腔约束

机械“不是……而是……”“不再是……而是……”“没有再……而是……”及“不是……——是……”等变体是核心禁区，不判断为合理修辞。若 profile 证据显示作者常做否定纠偏，只提取其认知二分、信息反转、讽刺顿挫或叙述者纠偏功能，落笔时改为动作、事实顺序、信息差或直接陈述。器官轮岗、万能占位、比喻依赖、抽象总结、模板转折和景物强制同步按约 2% 叙事单元密度门禁控制，孤立出现需复核，密集出现必须修订。不要反复写“他知道、她明白、他意识到”；把认知变化转化为选择、停顿、回避、误判、语气和潜台词。执行“证据之后停笔”：动作、意象、对白、沉默或物证已经传达含义时，不追加翻译潜台词、概括人物感受、宣布主题或解释“这意味着什么”的段尾、场尾句。

## 数字与量化细节

无关精确数字默认不用；“一个又一个”等虚指反复不按精确计数处理。真正精确值若承担当场问答、人物谈判、身份或债务辨认、选择、因果、连续性或后文核验中的一项实际功能，可保留，不要求五项同时成立。年龄、日期、规则编号等既定事实须准确。技术、灾难、悬疑、倒计时、场景合同和参考语料不自动豁免装饰性读数；普通陈设和日常动作不为显得具体而计件、计次或计秒。交稿前逐项判断数词是否真的提供精确值及其语境功能，删去无关精度时围绕状态、动作或后果重写，不批量删除，也不机械换成模糊量词。

## 禁止倾向

- 不摘抄连续原文。
- 不把风格简化为高频词堆叠。
- 不把候选事实写成已确认事实。
- 不用密集句号、长逗号链、机械“不是……而是……”“不再是……而是……”“没有再……而是……”或破折号堆叠伪装文学性。
- 不把“不是 A——是 B”式否定纠偏结构交给脚本批量删除；语义改写必须逐句复核。
- 不用 AI 腔、对称排比或抽象总结制造廉价文学感。
- 不把“克制”写成全程白描、同速句群和语气相同的人物；不在证据之后补解释性结论。
- 不为了贴近文风牺牲可读性、人物逻辑和剧情因果。

## 输出自检

- 是否保持叙述距离稳定。
- 是否把句法、标点、段落推进和意象调度落实成可执行约束。
- 是否让意象服务主题和人物状态。
- 是否在承压处出现有因果的句法、修辞、语域或叙述距离变化，并落实主参考样例的至少两项可观察技法。
- 是否删去动作、意象、对白或物证之后重复其含义的解释性尾句。
- 是否避免 AI 腔、机械对照句式、破折号转折变体，并让解释性心理标签、器官轮岗、万能占位、比喻依赖和金句化收束低于约 2% 密度门禁。
- 是否只保留有选择、连续性、辨认或后续兑现功能的精确数字，并对其余量化表达作了语义重写。
- 是否避免过短导致约束不足，或过长导致模型抓不住优先级。
- 是否保留人工确认点。
"""
    return {
        "schema": "literary-engineering-workbench/style-prompt-agent/v1",
        "prompt_markdown": prompt,
        "constraints": ["叙述距离", "句法节奏", "意象调度", "心理呈现", "对白动作", "量化细节"],
        "avoid": ["原文摘抄", "高频词机械堆叠", "候选事实冒充 canon", "装饰性精确数字"],
        "source_paths": source_paths,
        "evaluation_plan": ["back-translation", "outline-expansion", "blind-review"],
        "risk_notes": ["dry-run prompt is a contract sample; use http-chat for model-authored refinement."],
    }


def _resolve_output(root: Path, value: Path | None, default_name: str) -> Path:
    if value is None:
        return root / default_name
    return value if value.is_absolute() else root / value
