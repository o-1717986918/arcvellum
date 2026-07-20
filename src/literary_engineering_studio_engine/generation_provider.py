"""Pluggable scene generation provider interface."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol
from urllib import error, request

from .agent_tasks import default_agent_tasks_path, write_agent_tasks
from .anti_ai_style import ANTI_EVASION_SHORT_RULE
from .context_broker import default_context_trace_path
from .context_packet import build_context_packet
from .model_config import MODEL_PROVIDER_CHOICES, get_model_settings, resolve_model_provider
from .new_character_register import empty_new_character_register, render_new_character_register_contract
from .prompt_pack import build_scene_prompt_pack, write_prompt_manifest


GENERATION_PROVIDERS = MODEL_PROVIDER_CHOICES


@dataclass(frozen=True)
class GenerationRequest:
    project_root: Path
    scene_path: Path
    context_path: Path
    scene_id: str
    context_text: str
    system_prompt: str
    user_prompt: str
    prompt_sources: list[dict[str, object]]
    composition_path: Path | None
    style_profile_path: Path | None
    provider: str


@dataclass(frozen=True)
class GenerationResult:
    project_root: Path
    candidate_path: Path
    manifest_path: Path
    prompt_manifest_path: Path
    agent_tasks_path: Path | None
    provider: str
    scene_id: str
    generated_chars: int


class SceneGenerationProvider(Protocol):
    name: str

    def generate(self, request: GenerationRequest) -> str:
        """Return a draft candidate body."""


class DryRunProvider:
    name = "dry-run"

    def generate(self, request: GenerationRequest) -> str:
        excerpt = " ".join(request.user_prompt.split())[:1200]
        return f"""## 正文候选

这是 dry-run provider 生成的结构化候选，不是最终正文。它用于验证上下文注入、产物落盘、审查和后续模型接入链路。

场景 `{request.scene_id}` 的候选写作应基于以下上下文摘要推进：

> {excerpt}

请在接入真实模型 provider 后，将本段替换为符合人物 BDI、背景故事隐性动因、canon 约束和文风 profile 的场景正文。背景故事只能通过选择、回避、误判、语气和关系压力体现，不得直接解释成设定段落。

## 状态变化候选

### 新增事实候选

- 待真实 provider 补全，且必须等待人工确认。

### 人物状态变化

- 待真实 provider 补全。

### 关系变化

- 待真实 provider 补全。

### 伏笔变化

- 待真实 provider 补全。

### 需要人工确认

- dry-run 未产生可确认为 canon 的新事实。

## 新角色候选登记

- status: none
- introduced: []
- note: dry-run 未引入新角色；真实生成时必须写入 new_character_register。
"""


class HttpChatProvider:
    name = "http-chat"

    def generate(self, request_data: GenerationRequest) -> str:
        settings = get_model_settings(default_temperature=0.7, default_max_tokens=2500)
        if not settings.api_base or not settings.model:
            raise RuntimeError(
                "http-chat provider requires model config. Set LEW_MODEL_API_BASE and LEW_MODEL_NAME, "
                "or configure the global config file. Set LEW_MODEL_API_KEY, the configured api_key_env, or a saved profile api_key if needed."
            )
        if not settings.api_key:
            raise RuntimeError(f"http-chat provider requires an API key. Set LEW_MODEL_API_KEY, {settings.api_key_env}, or save api_key in the active profile.")
        payload = {
            "model": settings.model,
            "messages": [
                {"role": "system", "content": request_data.system_prompt},
                {"role": "user", "content": request_data.user_prompt},
            ],
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
            raise RuntimeError(f"http-chat provider request failed: HTTP {exc.code}. {details}") from exc
        except error.URLError as exc:
            raise RuntimeError(f"http-chat provider request failed: {exc.reason}") from exc
        data = json.loads(response_text)
        return _extract_chat_text(data)


def generate_scene_candidate(
    project_root: Path,
    scene: Path | None = None,
    context: Path | None = None,
    composition: Path | None = None,
    query: str = "",
    rebuild_context: bool = False,
    provider: str = "auto",
    output: Path | None = None,
    agent_tasks: bool = False,
    allow_unselected_composition: bool = False,
    allow_missing_composition: bool = False,
) -> GenerationResult:
    root = project_root.resolve()
    if not root.is_dir():
        raise FileNotFoundError(f"project root not found: {root}")
    resolved_provider = resolve_model_provider(provider, purpose="scene generation")

    scene_path = root / "scenes" / "scene_0001.yaml" if scene is None else (scene if scene.is_absolute() else root / scene)
    if not scene_path.exists():
        raise FileNotFoundError(f"scene file not found: {scene_path}")
    scene_id = scene_path.stem or "scene"

    context_path = context if context and context.is_absolute() else (
        root / context if context else root / "memory" / "context_packets" / f"{scene_id}.md"
    )
    if rebuild_context or not context_path.exists() or not default_context_trace_path(context_path).exists():
        context_result = build_context_packet(root, scene=scene_path, query=query, rebuild_index=True, output=context_path)
        context_path = context_result.output_path
    context_text = context_path.read_text(encoding="utf-8", errors="ignore").strip()
    if not context_text:
        raise FileNotFoundError(f"context packet not found or empty: {context_path}")
    prompt_pack = build_scene_prompt_pack(
        root,
        scene_path,
        context_path,
        composition=composition,
        allow_unselected_composition=allow_unselected_composition,
        allow_missing_composition=allow_missing_composition,
    )

    provider_impl = _provider_for(resolved_provider)
    request = GenerationRequest(
        project_root=root,
        scene_path=scene_path,
        context_path=context_path,
        scene_id=scene_id,
        context_text=context_text,
        system_prompt=prompt_pack.system_prompt,
        user_prompt=prompt_pack.user_prompt,
        prompt_sources=prompt_pack.sources,
        composition_path=prompt_pack.composition_path,
        style_profile_path=prompt_pack.style_profile_path,
        provider=resolved_provider,
    )
    body = provider_impl.generate(request)
    candidate_path = output if output and output.is_absolute() else (
        root / output if output else _default_candidate_path(root, scene_id, resolved_provider)
    )
    candidate_path.parent.mkdir(parents=True, exist_ok=True)
    prompt_manifest_path = candidate_path.with_suffix(".prompt.json")
    write_prompt_manifest(prompt_pack, prompt_manifest_path, provider=resolved_provider, model=_model_label(resolved_provider))
    rendered = _render_candidate(request, body)
    candidate_path.write_text(rendered, encoding="utf-8")
    manifest_path = candidate_path.with_suffix(".json")
    manifest = {
        "schema": "literary-engineering-workbench/scene-generation-candidate/v0.1",
        "provider": resolved_provider,
        "requested_provider": provider,
        "scene_id": scene_id,
        "scene": _rel_str(scene_path, root),
        "context": _rel_str(context_path, root),
        "composition": _rel_str(prompt_pack.composition_path, root) if prompt_pack.composition_path else "",
        "style_profile": _rel_str(prompt_pack.style_profile_path, root) if prompt_pack.style_profile_path else "",
        "candidate": _rel_str(candidate_path, root),
        "prompt_manifest": _rel_str(prompt_manifest_path, root),
        "generated_at": _now(),
        "generated_chars": len(rendered),
        "prompt_sources": prompt_pack.sources,
        "reader_experience_contract": prompt_pack.reader_experience_contract,
        "new_character_register": empty_new_character_register(),
        "request": {
            key: str(value) if isinstance(value, Path) else value
            for key, value in asdict(request).items()
            if key not in {"context_text", "system_prompt", "user_prompt"}
        },
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    agent_tasks_path = None
    if agent_tasks:
        agent_tasks_path = _write_generation_agent_tasks(
            root,
            scene_path,
            context_path,
            candidate_path,
            manifest_path,
            prompt_manifest_path,
            prompt_pack.composition_path,
            prompt_pack.style_profile_path,
        )
    return GenerationResult(
        project_root=root,
        candidate_path=candidate_path,
        manifest_path=manifest_path,
        prompt_manifest_path=prompt_manifest_path,
        agent_tasks_path=agent_tasks_path,
        provider=resolved_provider,
        scene_id=scene_id,
        generated_chars=len(rendered),
    )


def _write_generation_agent_tasks(
    root: Path,
    scene_path: Path,
    context_path: Path,
    candidate_path: Path,
    manifest_path: Path,
    prompt_manifest_path: Path,
    composition_path: Path | None,
    style_profile_path: Path | None,
) -> Path:
    context_trace_path = default_context_trace_path(context_path)
    sources = [scene_path, context_path, candidate_path, manifest_path, prompt_manifest_path]
    if context_trace_path.exists():
        sources.insert(2, context_trace_path)
    if composition_path:
        sources.append(composition_path)
    if style_profile_path:
        sources.append(style_profile_path)
    new_character_contract = render_new_character_register_contract()
    return write_agent_tasks(
        default_agent_tasks_path(candidate_path),
        title=f"generate-scene {scene_path.stem}",
        root=root,
        source_paths=sources,
        notes=[
            "prompt manifest 是审计证据，不能写入 AGENT_TASK 标记。",
            "candidate markdown 是模型候选，不是正稿；进入 drafts/scenes 前必须审查。",
        ],
        tasks=[
            (
                "审查 prompt manifest",
                """读取 .prompt.json，确认 system/user messages、source files、composition、style_profile、generation_standards.style、generation_standards.word_budget、generation_standards.reader_experience_contract、generation_standards.review_notes、generation_standards.anti_evasion、generation_standards.hard_constraints、generation_standards.new_character_register、provider 和 model 是否完整。检查是否遗漏 canon、character facts、scene goal、mounted style skill、文风生成标准、长篇字数预算标准、读者体验硬属性、新角色登记契约、AgentReview 小修约束、反规避协议、生成前最终硬约束摘要或用户约束。""",
            ),
            (
                "审查反规避执行",
                f"""检查候选是否像是在生成前执行过 generation_standards.anti_evasion。{ANTI_EVASION_SHORT_RULE} 若候选把信息反转写成“看似……其实……”等换皮转折，视为阻塞；建议改为动作、事实顺序、信息差、物证或直接陈述。""",
            ),
            (
                "审查生成前硬约束摘要",
                """检查候选是否像是在生成前执行过 generation_standards.hard_constraints：canon/用户约束、场景编排、人物逻辑、文风、字数预算、AgentReview 小修、标点和输出边界是否形成明确优先级。若正文暴露工作流痕迹、跳过上位约束或把候选写成 canon，标为阻塞。""",
            ),
            (
                "审查生成前文风标准",
                """检查候选是否像是在生成前执行过 generation_standards.style：叙述距离、句法/段落节奏、意象/感官系统、心理呈现、对白密度与语气、标点停顿节奏是否已经进入正文机制，而不是只在审查阶段被口头声明。""",
            ),
            (
                "审查 AgentReview 小修执行",
                """若 prompt manifest 中 generation_standards.review_notes_loaded=true，尤其上一轮为 pass_with_notes，检查候选是否执行了 revision_actions、warnings 和 style_notes。允许局部微调，但不允许静默忽略；无法执行的项必须进入“需要人工确认”。""",
            ),
            (
                "审查生成前字数预算标准",
                """若 prompt manifest 中 generation_standards.word_budget_loaded=true，检查候选是否服从长篇预算：本场景承担的剧情功能、信息变化、关系压力、后果链和章节节奏是否支撑预算，而不是把有限事件拉长或压缩为摘要。若预算缺失或 needs_expansion，说明是否应暂停批量生成。""",
            ),
            (
                "审查读者体验硬属性",
                """若 prompt manifest 中 generation_standards.reader_experience_loaded=true，检查候选是否执行本场读者问题、承诺回报、暂扣信息、兑现/延迟、情绪曲线、张力来源、新鲜度、反摘要要求和读后余味。若正文只完成事件摘要、没有推进读者期待或没有形成章节承诺的支付/延迟，标为阻塞。""",
            ),
            (
                "审查候选正文",
                """读取候选正文，判断它是否服从 prompt manifest、scene.yaml、context packet、context trace、composition 和 style prompt。标出人物 OOC、canon 冲突、background_story 直白化、风格偏离、不确定新增事实，以及正文中新出现但未在 scene.yaml 或正式 characters 中登记的人物。若 trace 缺失或显示必需上下文未加载，不得建议进入 promote。""",
            ),
            (
                "执行新角色登记门禁",
                f"""{new_character_contract}

检查候选 Markdown 的 `## 新角色候选登记` 和候选 manifest 的 `new_character_register`。若正文没有新角色，manifest 写 `status=none`；若只有一次性路人，写 `status=ephemeral_only` 并给出 waiver_reason；若出现命名、可复用、掌握线索、推动关系或改变世界状态的新角色，必须进入 candidate asset、review、approval/promotion 链路。未解决时不得建议 promote。""",
            ),
            (
                "决定下一步",
                """决定候选应进入 review-scene、返回 generate-scene 重写、人工修订，还是保留为废弃候选。不得直接 promote；如建议 promote，先写清选择理由和需要用户确认的事项。""",
            ),
            (
                "整理写回风险",
                """从候选中的状态变化候选区域和 new_character_register 提取新增事实、人物状态、关系、伏笔变化和新角色候选，标记哪些需要后续 state-evolve、asset-create、review-candidate-asset、canon-lint 或用户批准。""",
            ),
        ],
    )


def _provider_for(provider: str) -> SceneGenerationProvider:
    if provider == "dry-run":
        return DryRunProvider()
    if provider == "http-chat":
        return HttpChatProvider()
    raise ValueError(f"unknown generation provider: {provider}")


def _render_candidate(request: GenerationRequest, body: str) -> str:
    return f"""# Scene Generation Candidate：{request.scene_id}

- Provider：`{request.provider}`
- Scene：`{_rel_str(request.scene_path, request.project_root)}`
- Context：`{_rel_str(request.context_path, request.project_root)}`
- Composition：`{_rel_str(request.composition_path, request.project_root) if request.composition_path else 'n/a'}`
- Generated At：{_now()}

## 使用边界

- 本文件是模型候选，不是正稿。
- 进入 `drafts/scenes/` 前必须经过人工选择、修订和 `review-scene`。
- 新事实只能作为候选，不得直接写入 canon。
- 人物 `background_story` 只能作为隐性行为因果，不得在正文中直白交代。

{body.strip()}
"""


def _default_candidate_path(root: Path, scene_id: str, provider: str) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return root / "drafts" / "candidates" / f"{scene_id}-{provider}-{stamp}.md"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


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
    raise RuntimeError("http-chat provider response did not contain generated text")


def _model_label(provider: str) -> str:
    if provider == "http-chat":
        return get_model_settings().model
    return provider


def _rel_str(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root).as_posix()
    except ValueError:
        return str(path)
