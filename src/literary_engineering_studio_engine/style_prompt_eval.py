"""Run LLM-backed style prompt effectiveness evaluations."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib import error, request

from .model_config import get_model_settings, resolve_model_provider
from .punctuation_standard import PUNCTUATION_STANDARD_PROMPT
from .style_evaluator import STYLE_EVAL_MODES, StyleEvalOptions, evaluate_style
from .style_prompt import STYLE_PROMPT_PROVIDERS


@dataclass(frozen=True)
class StylePromptEvalResult:
    candidate_path: Path
    prompt_manifest_path: Path
    report_path: Path
    metrics_path: Path
    mode: str
    provider: str
    overall_score: float
    risk_level: str


def run_style_prompt_eval(
    profile_dir: Path,
    reference: Path,
    task_input: Path,
    mode: str = "back-translation",
    provider: str = "auto",
    style_prompt: Path | None = None,
    out_dir: Path | None = None,
) -> StylePromptEvalResult:
    """Generate a candidate with a style prompt, then evaluate prompt effectiveness."""

    if mode not in STYLE_EVAL_MODES:
        raise ValueError(f"unknown style eval mode: {mode}. valid: {', '.join(sorted(STYLE_EVAL_MODES))}")
    resolved_provider = resolve_model_provider(provider, purpose="style prompt effectiveness evaluation")

    profile_root = profile_dir.resolve()
    reference_path = reference.resolve()
    input_path = task_input.resolve()
    if not profile_root.is_dir():
        raise FileNotFoundError(f"profile dir not found: {profile_root}")
    if not reference_path.is_file():
        raise FileNotFoundError(f"reference text not found: {reference_path}")
    if not input_path.is_file():
        raise FileNotFoundError(f"task input not found: {input_path}")
    style_prompt_path = (style_prompt.resolve() if style_prompt else profile_root / "style_prompt.md")
    if not style_prompt_path.is_file():
        raise FileNotFoundError(f"style prompt not found: {style_prompt_path}. run style-prompt first")

    eval_dir = (out_dir or profile_root / "evaluation_results" / mode).resolve()
    eval_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    candidate_path = eval_dir / f"style_prompt_candidate_{stamp}.txt"
    prompt_manifest_path = eval_dir / f"style_prompt_candidate_{stamp}.prompt.json"
    messages = _messages(style_prompt_path, input_path, mode)
    candidate_text = _generate(resolved_provider, messages, mode)
    candidate_path.write_text(candidate_text.strip() + "\n", encoding="utf-8")
    prompt_manifest = {
        "schema": "literary-engineering-workbench/style-prompt-eval-generation/v0.1",
        "generated_at": _now(),
        "provider": resolved_provider,
        "requested_provider": provider,
        "model": _model_label(resolved_provider),
        "mode": mode,
        "style_prompt": str(style_prompt_path),
        "reference": str(reference_path),
        "task_input": str(input_path),
        "candidate": str(candidate_path),
        "messages": messages,
    }
    prompt_manifest_path.write_text(json.dumps(prompt_manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    evaluated = evaluate_style(
        StyleEvalOptions(
            profile_dir=profile_root,
            reference=reference_path,
            candidate=candidate_path,
            mode=mode,
            out_dir=eval_dir,
        )
    )
    return StylePromptEvalResult(
        candidate_path=candidate_path,
        prompt_manifest_path=prompt_manifest_path,
        report_path=evaluated.report_path,
        metrics_path=evaluated.metrics_path,
        mode=mode,
        provider=resolved_provider,
        overall_score=evaluated.overall_score,
        risk_level=evaluated.risk_level,
    )


def _messages(style_prompt_path: Path, input_path: Path, mode: str) -> list[dict[str, str]]:
    style_prompt = style_prompt_path.read_text(encoding="utf-8", errors="ignore").strip()
    task_input = input_path.read_text(encoding="utf-8", errors="ignore").strip()
    if mode == "back-translation":
        task = "请把输入英文回译为中文，目标是验证文风约束提示词是否能让 LLM 复现目标风格机制。"
    elif mode == "outline-expansion":
        task = "请把输入大纲扩写为中文正文，目标是验证文风约束提示词是否能让 LLM 复现目标风格机制。"
    else:
        task = "请根据输入生成一段中文候选文本，用于盲评文风归属和提示词有效性。"
    system = f"""{style_prompt}

你现在进入文风提示词有效性测试。必须只输出候选正文，不输出分析过程。"""
    user = f"""{task}

## 标准中文标点约束

{PUNCTUATION_STANDARD_PROMPT}

## 输入

{task_input}

## 输出要求

- 只输出中文候选正文。
- 候选正文必须遵守标准中文标点约束，除非输入明确要求保留原始异常标点。
- 不确认 canon，不写审查报告。
- 不摘抄参考文本或原文连续片段。
"""
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def _generate(provider: str, messages: list[dict[str, str]], mode: str) -> str:
    if provider == "dry-run":
        input_excerpt = " ".join(messages[-1]["content"].split())[:500]
        return (
            "雨落在旧城的石桥上，灯影被水面慢慢揉碎。林舟沿着河岸停了停，像是在听一件没有说出口的事。"
            "他知道沉默并不总是安全，有时只是危险换了一种更轻的声音。"
            f"\n\n（dry-run {mode} 输入摘要：{input_excerpt}）"
        )
    if provider == "http-chat":
        return _http_chat(messages)
    raise ValueError(f"unknown style prompt eval provider: {provider}")


def _http_chat(messages: list[dict[str, str]]) -> str:
    settings = get_model_settings(default_temperature=0.5, default_max_tokens=1800)
    if not settings.api_base or not settings.model:
        raise RuntimeError(
            "style-prompt-eval http-chat provider requires model config. Set LEW_MODEL_API_BASE and LEW_MODEL_NAME, "
            "or configure the global config file. Set LEW_MODEL_API_KEY, the configured api_key_env, or a saved profile api_key if needed."
        )
    if not settings.api_key:
        raise RuntimeError(
            f"style-prompt-eval http-chat provider requires an API key. Set LEW_MODEL_API_KEY, {settings.api_key_env}, or save api_key in the active profile."
        )
    payload = {"model": settings.model, "messages": messages, "temperature": settings.temperature, "max_tokens": settings.max_tokens}
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {settings.api_key}"}
    req = request.Request(_chat_url(settings.api_base), data=body, headers=headers, method="POST")
    try:
        with request.urlopen(req, timeout=settings.timeout) as response:
            response_text = response.read().decode("utf-8", errors="ignore")
    except error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="ignore")[:800]
        raise RuntimeError(f"style-prompt-eval provider request failed: HTTP {exc.code}. {details}") from exc
    except error.URLError as exc:
        raise RuntimeError(f"style-prompt-eval provider request failed: {exc.reason}") from exc
    data = json.loads(response_text)
    return _extract_chat_text(data)


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
    raise RuntimeError("style-prompt-eval provider response did not contain generated text")


def _model_label(provider: str) -> str:
    if provider == "http-chat":
        return get_model_settings().model
    return provider


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
