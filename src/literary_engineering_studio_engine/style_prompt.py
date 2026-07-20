"""Build LLM-facing style constraint prompts from a style profile."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib import error, request

from .anti_ai_style import ANTI_AI_STYLE_PROMPT
from .model_config import MODEL_PROVIDER_CHOICES, get_model_settings, resolve_model_provider
from .punctuation_standard import PUNCTUATION_STANDARD_PROMPT
from .text_counts import CHINESE_CONTENT_COUNT_UNIT, count_chinese_content_chars


STYLE_PROMPT_PROVIDERS = MODEL_PROVIDER_CHOICES
STYLE_PROMPT_MIN_DETAIL_CHARS = 500
STYLE_PROMPT_MAX_DETAIL_CHARS = 2500
STYLE_PROMPT_LENGTH_RULE = (
    "可靠且可挂载的 LLM 文风约束提示词必须足够详细但可执行："
    f"按中文内容字符计算为 {STYLE_PROMPT_MIN_DETAIL_CHARS}-{STYLE_PROMPT_MAX_DETAIL_CHARS} 字，"
    "计入汉字和中文标点，不计入 Markdown 标记、代码围栏、英文路径或空白。"
)
STYLE_PROMPT_REQUIRED_BLOCKS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("使用身份与适用边界", ("使用身份", "使用边界", "适用边界", "优先级", "适用范围")),
    ("核心风格机制", ("核心风格", "风格机制", "叙事机制", "核心约束")),
    ("叙述距离与视角", ("叙述距离", "叙述视角", "视角", "叙述者")),
    ("句法与节奏", ("句法", "节奏", "句长", "段落")),
    ("标点节奏", ("标点", "句号", "逗号", "破折号")),
    ("意象与感官调度", ("意象", "感官", "视觉", "听觉", "触觉")),
    ("心理呈现与行为因果", ("心理", "行为", "动作", "背景故事", "隐性行为因果")),
    ("对白与语气", ("对白", "语气", "话语", "说话")),
    ("AI腔控制", ("AI腔", "AI痕迹", "模型腔", "模板化", "机械对照", "不是……而是", "不是……——是")),
    ("禁止倾向", ("禁止", "避免", "不得", "不要")),
    ("输出自检", ("自检", "检查", "输出前", "评估")),
)
STYLE_PROMPT_QUALITY_RULE = (
    "高质量文风 prompt 必须具备可执行结构：身份/边界、核心风格机制、叙述距离、句法节奏、"
    "标点节奏、意象感官、心理/行为因果、对白语气、AI 腔控制、禁止倾向和输出自检。"
)


@dataclass(frozen=True)
class StylePromptResult:
    profile_dir: Path
    output_path: Path
    manifest_path: Path
    provider: str
    generated_chars: int


def build_style_prompt(
    profile_dir: Path,
    provider: str = "auto",
    output: Path | None = None,
    manifest_output: Path | None = None,
) -> StylePromptResult:
    """Generate an LLM-facing style constraint prompt from compiled style assets."""

    profile_root = profile_dir.resolve()
    if not profile_root.is_dir():
        raise FileNotFoundError(f"profile dir not found: {profile_root}")
    resolved_provider = resolve_model_provider(provider, purpose="style prompt generation")

    profile_path = profile_root / "style-profile.md"
    metrics_path = profile_root / "style_metrics.json"
    manifest_path = profile_root / "corpus_manifest.yaml"
    if not profile_path.exists():
        raise FileNotFoundError(f"style profile not found: {profile_path}")
    if not metrics_path.exists():
        raise FileNotFoundError(f"style metrics not found: {metrics_path}")

    messages = _messages(profile_path, metrics_path, manifest_path)
    body = _generate(resolved_provider, messages)
    rendered = _render_style_prompt(resolved_provider, body)
    output_path = _resolve(profile_root, output, profile_root / "style_prompt.md")
    prompt_manifest_path = _resolve(profile_root, manifest_output, profile_root / "style_prompt.prompt.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    prompt_manifest_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(rendered, encoding="utf-8")
    prompt_manifest = {
        "schema": "literary-engineering-workbench/style-prompt/v0.1",
        "generated_at": _now(),
        "provider": resolved_provider,
        "requested_provider": provider,
        "model": _model_label(resolved_provider),
        "profile_dir": str(profile_root),
        "style_profile": str(profile_path),
        "style_metrics": str(metrics_path),
        "corpus_manifest": str(manifest_path) if manifest_path.exists() else "",
        "output": str(output_path),
        "messages": messages,
        "guardrails": [
            "本文件是供 LLM 使用的文风约束提示词，不是原文摘抄。",
            STYLE_PROMPT_LENGTH_RULE,
            "文风标点节奏必须建立在标准中文标点约束之上。",
            "精确模仿仅限公版或授权语料；其他语料只抽象叙事机制。",
            "后续回译、扩写和盲评应审查本提示词是否让 LLM 稳定复现目标风格机制。",
        ],
    }
    prompt_manifest_path.write_text(json.dumps(prompt_manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return StylePromptResult(
        profile_dir=profile_root,
        output_path=output_path,
        manifest_path=prompt_manifest_path,
        provider=resolved_provider,
        generated_chars=count_style_prompt_detail_chars(rendered),
    )


def _messages(profile_path: Path, metrics_path: Path, manifest_path: Path) -> list[dict[str, str]]:
    profile_text = _read(profile_path)
    metrics_text = _read(metrics_path)
    manifest_text = _read(manifest_path) if manifest_path.exists() else "未找到 corpus_manifest.yaml。"
    system = """你是文学工程工作台的文风约束提示词编译器。

你的输出不是评论文章，也不是风格报告，而是“供另一个 LLM 写作时直接使用的文风约束提示词”。

要求：

- 把 profile 和 metrics 转译成可执行的写作约束。
- 提示词正文必须足够详细但可执行，按中文内容字符计算控制在 500-2500 字之间；计入汉字和中文标点，不计入 Markdown 标记、代码围栏、英文路径或空白。低于 500 字通常无法稳定约束文风，高于 2500 字容易稀释优先级和造成执行漂移。
- 按优秀系统提示词标准写作：先定义使用身份、适用边界和优先级，再给出证据导向的可执行规则；每条规则应说明“做什么、为什么、何时例外、如何自检”，避免空泛形容词。
- 约束必须覆盖叙述距离、句法节奏、标点节奏、感官意象、心理描写、对白比例、AI 腔控制、禁忌倾向和自检规则。
- 标点部分必须区分“风格节奏”和“基础规范”：可以学习密度、停顿和句式，但不得输出中英标点混用、错误省略号、错误破折号、密集碎句、长逗号链、破折号滥用或机械转折词堆叠。
- 不要把作者风格简化为“句号很多”“破折号很多”“但是/然而很多”。必须说明句号、逗号、分号和转折词分别服务什么叙事功能；若作者证据中存在高破折号或否定纠偏结构，只能抽象其节奏、讽刺、信息反转或叙述者纠偏功能，不能把“不是……而是……”及“不是……——是……”作为可复制句式授权给生成模型。
- 降低 AI 腔部分必须采用“核心禁区 + 密度门禁”的写法：机械“不是……而是……”“并非……而是……”“与其说……不如说……”及“不是……——是……”变体是核心禁区，不判断为合理修辞；器官轮岗、万能占位、比喻依赖、抽象总结、模板转折和景物强制同步按约 2% 叙事单元密度控制，孤例复核，密集修订。
- 不摘抄原文，不制造不可验证的作者论断。
- 精确复现只适用于公版或授权语料；否则写成高层技法约束。
- 输出 Markdown，只输出提示词正文，不解释生成过程。
"""
    user = f"""请根据以下风格 profile、统计指标和语料 manifest，生成一份可直接注入 LLM 的文风约束提示词。

字数要求：提示词正文必须在 500-2500 中文内容字符之间，计入汉字和中文标点，不计入 Markdown 标记、代码围栏、英文路径或空白；宁可压缩空泛说明，也不能省略可执行约束。

质量要求：必须像正式 system prompt 一样清楚、可执行、可审查。至少覆盖使用身份/适用边界、核心风格机制、叙述距离与视角、句法与节奏、标点节奏、意象与感官、心理呈现与行为因果、对白与语气、AI 腔控制、禁止倾向、输出自检。避免“优美、克制、文学性强”等不能执行的空泛评价，改写成具体动作和判断标准。

输出必须包含：

## 使用身份
## 适用边界与优先级
## 核心风格机制
## 句法与节奏约束
## 叙述距离与心理呈现
## 意象和感官调度
## 对白与动作约束
## 降低 AI 腔约束
## 标点规范边界
## 禁止倾向
## 输出自检

### 标准中文标点约束

{PUNCTUATION_STANDARD_PROMPT}

### 降低 AI 腔约束

{ANTI_AI_STYLE_PROMPT}

### style-profile.md

{profile_text}

### style_metrics.json

```json
{metrics_text}
```

### corpus_manifest.yaml

```yaml
{manifest_text}
```
"""
    return [{"role": "system", "content": system.strip()}, {"role": "user", "content": user.strip()}]


def _generate(provider: str, messages: list[dict[str, str]]) -> str:
    if provider == "dry-run":
        return _dry_run_prompt(messages)
    if provider == "http-chat":
        return _http_chat(messages)
    raise ValueError(f"unknown style prompt provider: {provider}")


def _dry_run_prompt(messages: list[dict[str, str]]) -> str:
    user = messages[-1]["content"]
    excerpt = " ".join(user.split())[:1400]
    return f"""## 使用身份

你是一个遵守文学工程约束的长篇虚构文本生成 LLM。你必须依据本文风约束提示词生成候选正文，而不是复述语料、解释理论或确认 canon。

## 核心风格机制

- 先维持 profile 中的叙述距离、句法节奏和感官倾向，再处理局部词汇。
- 文风相似来自叙事机制、节奏、意象组织和心理呈现，不来自机械复用高频词。
- 所有风格选择必须服务当前项目 canon、人物 BDI、场景目标和冲突压力。

## 句法与节奏约束

- 句长、段长和标点节奏应参考 style_metrics，但不能机械复刻标点表面频率。
- 标点节奏必须建立在标准中文标点和文学节奏之上：中文正文使用全角标点，省略号用“……”，不要混用英文标点、连续堆叠感叹/疑问符、密集碎句、长逗号链或破折号滥用。
- 句号用于语义、镜头或心理落点；逗号用于未完成的动作、感知、心理和因果关系；分号用于并列层级；正式正文原则上不用破折号，孤立破折号需逐句语义复核，超过约 2% 叙事单元密度或替代转折时必须修订。
- 转折优先由动作、意象、视线变化、信息差和因果推进完成，少用“但是、然而、于是、然后、突然”式机械接榫。
- 长短句交替必须配合人物注意力变化、场景压迫和情绪拐点。
- 不要为了模仿而堆叠复杂句；节奏必须让事件推进更清晰。

## 叙述距离与心理呈现

- 心理描写密度应参考 profile 的 thought_density。
- 人物判断通过迟疑、回避、误判、沉默和动作折返表现，避免说明书式内心剖白。
- 叙述者态度要稳定，不在同一场景中随意从冷静观察跳到夸张评判。

## 意象和感官调度

- 优先使用 profile 中占比最高的感官通道组织场景。
- 意象必须与主题、人物状态和场景空间绑定，不作为孤立装饰。
- 同一意象可重复，但每次重复应带来信息、情绪或关系的变化。

## 对白与动作约束

- 对白比例参考 dialogue_density；对白应带有信息差、遮掩和关系压力。
- 动作描写必须体现人物目标和道德边界。
- 背景故事只作为隐性行为因果，不得直白解释为设定段。

## 降低 AI 腔约束

- 机械“不是……而是”及“不是……——是”等变体是核心禁区，不判断为合理修辞；把其原本想承担的认知二分、信息反转、讽刺顿挫或叙述者纠偏功能改写为动作、事实顺序、信息差或直接陈述。
- “某种意义、答案、真相、命运、这一刻、仿佛、像是”等抽象词，器官轮岗、万能占位、比喻依赖和模板转折按约 2% 叙事单元密度门禁控制；孤立出现需复核，密集出现必须修订。
- 不反复写“他知道、她明白、他意识到”；把认知变化转化为选择、停顿、回避、误判、语气和潜台词。
- 转折应来自因果、场景物理变化、人物目标冲突或伏笔回响，不靠连接词硬接。
- 结尾落在动作结果、关系变化、信息揭示或悬念上，不用金句化总结。

## 禁止倾向

- 不摘抄或改写原文连续片段。
- 不把风格简化为几个高频字词或固定比喻。
- 不为追求文风牺牲 canon、一致性、人物逻辑和场景输出状态。
- 不把候选事实写成已确认事实。

## 输出自检

- 句法节奏是否接近 profile，而不是只换词。
- 感官通道是否稳定服务场景目标。
- 心理描写和对白密度是否与 profile 相容。
- 标点是否符合标准中文标点与文学节奏约束，同时保留了 profile 所需的叙事功能，而不是机械复制标点频率。
- 是否降低 AI 腔：没有机械对照和破折号转折变体；抽象总结、解释性心理标签、模板化转折、对称排比、器官轮岗、万能占位、比喻依赖和金句化收束未超过约 2% 密度门禁。
- 是否避免复制原文连续表达。
- 是否保留了所有需要人工确认的 canon、人物和伏笔变化。

<!-- dry-run evidence: {excerpt} -->
"""


def _http_chat(messages: list[dict[str, str]]) -> str:
    settings = get_model_settings(default_temperature=0.4, default_max_tokens=2200)
    if not settings.api_base or not settings.model:
        raise RuntimeError(
            "style-prompt http-chat provider requires model config. Set LEW_MODEL_API_BASE and LEW_MODEL_NAME, "
            "or configure the global config file. Set LEW_MODEL_API_KEY, the configured api_key_env, or a saved profile api_key if needed."
        )
    if not settings.api_key:
        raise RuntimeError(
            f"style-prompt http-chat provider requires an API key. Set LEW_MODEL_API_KEY, {settings.api_key_env}, or save api_key in the active profile."
        )
    payload = {
        "model": settings.model,
        "messages": messages,
        "temperature": settings.temperature,
        "max_tokens": settings.max_tokens,
    }
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {settings.api_key}"}
    req = request.Request(_chat_url(settings.api_base), data=body, headers=headers, method="POST")
    try:
        with request.urlopen(req, timeout=settings.timeout) as response:
            response_text = response.read().decode("utf-8", errors="ignore")
    except error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="ignore")[:800]
        raise RuntimeError(f"style-prompt provider request failed: HTTP {exc.code}. {details}") from exc
    except error.URLError as exc:
        raise RuntimeError(f"style-prompt provider request failed: {exc.reason}") from exc
    data = json.loads(response_text)
    return _extract_chat_text(data)


def _render_style_prompt(provider: str, body: str) -> str:
    return f"""# LLM 文风约束提示词

- Provider：`{provider}`
- Generated At：{_now()}

## 使用边界

- 本文件是供 LLM 写作时注入的文风约束提示词。
- 它约束叙事机制、句法节奏、意象系统和心理呈现，不负责确认 canon。
- 可靠可挂载版本的正文中文内容字符应保持在 {STYLE_PROMPT_MIN_DETAIL_CHARS}-{STYLE_PROMPT_MAX_DETAIL_CHARS} 字之间，计入汉字和中文标点，不计入 Markdown 标记、代码围栏、英文路径或空白。
- 回译、扩写和盲评评测应审查“本提示词是否有效”，而不是只审查统计报告。

{body.strip()}
"""


def _chat_url(api_base: str) -> str:
    base = api_base.rstrip("/")
    if base.endswith("/chat/completions"):
        return base
    return base + "/chat/completions"


def _extract_chat_text(data: dict[str, object]) -> str:
    if isinstance(data.get("output_text"), str):
        return str(data["output_text"])
    if isinstance(data.get("content"), str):
        return str(data["content"])
    choices = data.get("choices")
    if isinstance(choices, list) and choices:
        first = choices[0]
        if isinstance(first, dict):
            message = first.get("message")
            if isinstance(message, dict) and isinstance(message.get("content"), str):
                return str(message["content"])
            if isinstance(first.get("text"), str):
                return str(first["text"])
    raise RuntimeError("style-prompt provider response did not contain generated text")


def _resolve(root: Path, value: Path | None, default: Path) -> Path:
    if value is None:
        return default
    return value if value.is_absolute() else root / value


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore").strip()


def count_style_prompt_detail_chars(text: str) -> int:
    """Count executable prompt detail as Chinese content characters."""

    total = 0
    in_fence = False
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if line.startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence or not line:
            continue
        if line.startswith("<!--") and line.endswith("-->"):
            continue
        line = re.sub(r"^#{1,6}\s*", "", line)
        line = re.sub(r"^[-*+]\s+", "", line)
        line = re.sub(r"^\d+[.)]\s+", "", line)
        line = line.replace("`", "")
        total += count_chinese_content_chars(line)
    return total


def style_prompt_quality_report(text: str) -> dict[str, object]:
    compact = re.sub(r"\s+", "", text)
    present: list[str] = []
    missing: list[str] = []
    for label, keywords in STYLE_PROMPT_REQUIRED_BLOCKS:
        if any(keyword in compact for keyword in keywords):
            present.append(label)
        else:
            missing.append(label)
    detail_chars = count_style_prompt_detail_chars(text)
    return {
        "detail_chars": detail_chars,
        "detail_count_unit": CHINESE_CONTENT_COUNT_UNIT,
        "count_note": "detail_chars counts Han characters and Chinese punctuation after stripping Markdown scaffolding.",
        "length_range": [STYLE_PROMPT_MIN_DETAIL_CHARS, STYLE_PROMPT_MAX_DETAIL_CHARS],
        "length_ok": STYLE_PROMPT_MIN_DETAIL_CHARS <= detail_chars <= STYLE_PROMPT_MAX_DETAIL_CHARS,
        "required_blocks": [label for label, _ in STYLE_PROMPT_REQUIRED_BLOCKS],
        "present_blocks": present,
        "missing_blocks": missing,
        "structure_ok": not missing,
    }


def _model_label(provider: str) -> str:
    if provider == "http-chat":
        return get_model_settings().model
    return provider


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
