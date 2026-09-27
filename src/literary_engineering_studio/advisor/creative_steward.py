"""Read-only delegated literary decision maker for bounded human-choice proposals."""

from __future__ import annotations

import json
from pathlib import Path
import re
import threading
from typing import Any, Callable

from literary_engineering_studio_engine.public.prompting import prompt_layer_spec, render_prompt_template

from .advisor_snapshot import create_advisor_snapshot, project_hashes
from ..runtime.role_conversation import RoleConversationGateway


DECISION_SCHEMA = "arcvellum/delegated-decision/v0.1"


class CreativeStewardCancelled(RuntimeError):
    """Raised when a paused autopilot run cancels a read-only decision."""


class CreativeSteward:
    def __init__(self, config: dict[str, Any], *, runtime_pool=None, event_sink=None,
                 prompt_resolver: Callable[[str, Path | None], str] | None = None):
        self.config = config
        self.runtime_pool = runtime_pool
        self.event_sink = event_sink
        self._prompt_resolver = prompt_resolver

    def decide(
        self,
        project_root: Path,
        choice: dict[str, Any],
        *,
        project_direction: str = "",
        timeout: int = 75,
        cancel_event: threading.Event | None = None,
    ) -> dict[str, Any]:
        options = [item for item in choice.get("options") or [] if isinstance(item, dict) and item.get("id")]
        if not options:
            raise ValueError("delegated choice does not contain selectable options")
        root = project_root.expanduser().resolve()
        before = project_hashes(root)
        data_root = Path(str(self.config.get("application", {}).get("data_root") or ".")).expanduser().resolve()
        snapshot = create_advisor_snapshot(root, data_root / "steward" / "snapshots")
        if cancel_event is not None and cancel_event.is_set():
            raise CreativeStewardCancelled("Creative Steward decision cancelled before it started")
        result = self._run(
            snapshot.workspace,
            choice,
            evidence_packet=_decision_evidence_packet(snapshot.workspace, choice),
            project_direction=project_direction,
            literary_guidance=self._literary_guidance(root),
            timeout=timeout,
            cancel_event=cancel_event,
        )
        if before != project_hashes(root):
            raise RuntimeError("Creative Steward read-only integrity check failed")
        allowed = {str(item["id"]) for item in options}
        selected = str(result.get("selected_option") or "")
        if selected not in allowed:
            raise RuntimeError("Creative Steward selected an option outside the proposal")
        result["schema"] = DECISION_SCHEMA
        result["decision_type"] = str(choice.get("decision_type") or "general_project_choice")
        result["choice_id"] = str(choice.get("choice_id") or "")
        result["project_snapshot_digest"] = snapshot.digest
        result["principal_type"] = "delegated-agent"
        result["principal_id"] = "creative-steward"
        return result

    def _literary_guidance(self, project_root: Path) -> str:
        return self._prompt_resolver("steward.identity", project_root) if self._prompt_resolver else ""

    def _run(
        self,
        workspace: Path,
        choice: dict[str, Any],
        *,
        evidence_packet: str,
        project_direction: str,
        literary_guidance: str,
        timeout: int,
        cancel_event: threading.Event | None,
    ) -> dict[str, Any]:
        return self._run_pi(
            workspace,
            choice,
            evidence_packet=evidence_packet,
            project_direction=project_direction,
            literary_guidance=literary_guidance,
            timeout=timeout,
            cancel_event=cancel_event,
        )

    def _run_pi(
        self,
        workspace: Path,
        choice: dict[str, Any],
        *,
        evidence_packet: str,
        project_direction: str,
        literary_guidance: str,
        timeout: int,
        cancel_event: threading.Event | None,
    ) -> dict[str, Any]:
        data_root = Path(str(self.config.get("application", {}).get("data_root") or ".")).expanduser().resolve()
        gateway = RoleConversationGateway(self.config, data_root=data_root)
        prompt = _decision_prompt(choice, project_direction, evidence_packet,
                                  literary_guidance=literary_guidance)
        self._emit("steward.session.started", {"runtime": "pi-worker"})
        try:
            conversation = gateway.run(
                workspace,
                prompt,
                role="steward",
                timeout=timeout,
                event_sink=self._forward_pi_event,
                cancel_event=cancel_event,
            )
            try:
                result = _parse_decision(conversation.answer)
                if not _has_declared_selection(result, choice):
                    raise RuntimeError("Creative Steward selected an option outside the proposal")
            except (RuntimeError, json.JSONDecodeError):
                self._emit("steward.decision.repair_started", {"runtime": "pi-worker"})
                repaired = gateway.run(
                    workspace,
                    prompt + "\n\n" + _decision_repair_prompt(choice),
                    role="steward",
                    timeout=timeout,
                    event_sink=self._forward_pi_event,
                    cancel_event=cancel_event,
                )
                result = _parse_decision(repaired.answer)
                if not _has_declared_selection(result, choice):
                    raise RuntimeError("Creative Steward selected an option outside the proposal after one repair attempt")
            self._emit(
                "steward.session.finished",
                {"runtime": "pi-worker", "model": conversation.model, "status": "complete"},
            )
            return result
        except Exception:
            self._emit("steward.session.finished", {"runtime": "pi-worker", "status": "failed"})
            raise

    def _forward_pi_event(self, event: str, data: dict[str, Any]) -> None:
        if event == "usage.updated":
            self._emit("steward.usage", data)
        elif event == "runner.warning":
            self._emit("steward.notice", data)

    def _emit(self, event: str, data: dict[str, Any]) -> None:
        if self.event_sink is not None:
            self.event_sink(event, data)


def _decision_prompt(choice: dict[str, Any], project_direction: str, evidence_packet: str = "",
                     *, literary_guidance: str = "") -> str:
    compact = {
        key: choice.get(key)
        for key in ("choice_id", "route", "decision_type", "title", "summary", "target", "source_paths", "recommended", "options")
    }
    return render_prompt_template("steward.decision.protocol", (
        literary_guidance.strip() or prompt_layer_spec("steward.identity").default_text,
        project_direction or "No additional direction was recorded.",
        _decision_scope_instruction(choice), json.dumps(compact, ensure_ascii=False, indent=2),
        evidence_packet or "No additional source file was supplied for this bounded choice.",
    ))


def _decision_scope_instruction(choice: dict[str, Any]) -> str:
    target = choice.get("target") if isinstance(choice.get("target"), dict) else {}
    scope = str(target.get("release_scope") or "").strip()
    if scope == "chapter-only":
        return prompt_layer_spec("steward.scope.chapter.protocol").default_text
    if scope == "whole-work-final":
        return prompt_layer_spec("steward.scope.final.protocol").default_text
    return prompt_layer_spec("steward.scope.default.protocol").default_text


def _decision_evidence_packet(workspace: Path, choice: dict[str, Any]) -> str:
    """Embed only declared decision evidence so steward sessions cannot wander the project."""

    root = workspace.resolve()
    fragments: list[str] = []
    remaining = 12_000
    source_paths = choice.get("source_paths") if isinstance(choice.get("source_paths"), list) else []
    for raw_path in source_paths:
        relative = str(raw_path or "").replace("\\", "/").strip().lstrip("/")
        if not relative or remaining <= 0:
            continue
        candidate = (root / relative).resolve()
        try:
            candidate.relative_to(root)
        except ValueError:
            continue
        if not candidate.is_file():
            fragments.append(f"<source path=\"{relative}\" status=\"missing\" />")
            continue
        try:
            content = candidate.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            fragments.append(f"<source path=\"{relative}\" status=\"unreadable\" />")
            continue
        excerpt = content[: min(4_000, remaining)]
        remaining -= len(excerpt)
        suffix = "\n[excerpt truncated]" if len(content) > len(excerpt) else ""
        fragments.append(f"<source path=\"{relative}\">\n{excerpt}{suffix}\n</source>")
    return "\n\n".join(fragments)


def _decision_repair_prompt(choice: dict[str, Any]) -> str:
    option_ids = [str(item.get("id") or "") for item in choice.get("options") or [] if isinstance(item, dict) and item.get("id")]
    return render_prompt_template("steward.repair.protocol", (json.dumps(option_ids, ensure_ascii=False),))


def _has_declared_selection(result: dict[str, Any], choice: dict[str, Any]) -> bool:
    selected = str(result.get("selected_option") or "")
    return selected in {
        str(item.get("id") or "")
        for item in choice.get("options") or []
        if isinstance(item, dict) and item.get("id")
    }

def _parse_decision(text: str) -> dict[str, Any]:
    candidate = text.strip()
    fenced = re.search(r"```(?:json)?\s*(\{.*\})\s*```", candidate, re.DOTALL)
    if fenced:
        candidate = fenced.group(1)
    elif not candidate.startswith("{"):
        start, end = candidate.find("{"), candidate.rfind("}")
        if start >= 0 and end > start:
            candidate = candidate[start : end + 1]
    if not candidate:
        raise RuntimeError("Creative Steward returned no decision JSON")
    try:
        payload = json.loads(candidate)
    except json.JSONDecodeError as exc:
        raise RuntimeError("Creative Steward returned invalid decision JSON") from exc
    if not isinstance(payload, dict):
        raise RuntimeError("Creative Steward decision must be an object")
    confidence = max(0.0, min(1.0, float(payload.get("confidence") or 0)))
    return {
        "selected_option": str(payload.get("selected_option") or ""),
        "rationale": str(payload.get("rationale") or ""),
        "evidence": payload.get("evidence") if isinstance(payload.get("evidence"), list) else [],
        "alternatives": payload.get("alternatives") if isinstance(payload.get("alternatives"), list) else [],
        "confidence": confidence,
        "requires_human": bool(payload.get("requires_human")),
        "human_reason": str(payload.get("human_reason") or ""),
    }
