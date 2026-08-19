"""Black-box continuous Pi Worker acceptance through the public Studio API."""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


TERMINAL_RUN_STATUSES = {"complete", "paused", "blocked", "cancelled", "failed"}
DELEGATED_DECISIONS = [
    "asset_approval", "branch_selection", "budget_expansion", "canon_patch_approval",
    "revision_direction", "state_patch_confirmation", "style_mount",
]


class StudioApi:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")

    def get(self, path: str, **query: object) -> dict[str, Any]:
        suffix = "?" + urlencode({key: value for key, value in query.items() if value not in {None, ""}}) if query else ""
        return self._request("GET", path + suffix)

    def send(self, method: str, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request(method, path, payload)

    def _request(self, method: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8") if payload is not None else None
        request = Request(
            self.base_url + path,
            data=body,
            method=method,
            headers={"Content-Type": "application/json"},
        )
        try:
            with urlopen(request, timeout=30) as response:
                value = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Studio API {method} {path} failed ({exc.code}): {detail[:1000]}") from exc
        except (URLError, TimeoutError) as exc:
            raise RuntimeError(f"Studio API is unavailable: {exc}") from exc
        if not isinstance(value, dict):
            raise RuntimeError(f"Studio API {method} {path} returned a non-object response")
        return value


@dataclass(frozen=True)
class LoopEvidence:
    runtime_is_pi: bool
    pi_session_seen: bool
    provider_request_seen: bool
    candidate_reviewed_and_promoted: bool
    promoted_draft_exists: bool
    state_applied: bool
    continuity_applied: bool
    next_scene_claimed: bool

    @property
    def complete(self) -> bool:
        return all(asdict(self).values())


@dataclass(frozen=True)
class FullWorkAcceptance:
    target_chapters: int
    target_scenes: int
    target_chinese_chars: int


@dataclass(frozen=True)
class FullWorkEvidence:
    runtime_is_pi: bool
    pi_session_seen: bool
    provider_request_seen: bool
    formal_chapter_count: int
    formal_scene_count: int
    promoted_scene_count: int
    passed_promotion_count: int
    reviewed_scene_count: int
    state_applied_count: int
    continuity_applied_count: int
    total_chinese_content_chars: int
    delivery_file_count: int
    delivery_status: str
    run_status: str
    acceptance: FullWorkAcceptance

    @property
    def complete(self) -> bool:
        expected_scenes = max(self.acceptance.target_scenes, self.formal_scene_count)
        return (
            self.runtime_is_pi
            and self.pi_session_seen
            and self.provider_request_seen
            and self.formal_chapter_count >= self.acceptance.target_chapters
            and self.formal_scene_count >= self.acceptance.target_scenes
            and self.promoted_scene_count >= expected_scenes
            and self.passed_promotion_count >= expected_scenes
            and self.reviewed_scene_count >= expected_scenes
            and self.state_applied_count >= expected_scenes
            and self.continuity_applied_count >= expected_scenes
            and self.total_chinese_content_chars >= self.acceptance.target_chinese_chars
            and self.delivery_file_count > 0
            and self.delivery_status == "ready"
            and self.run_status == "complete"
        )


def collect_evidence(
    project_root: Path,
    run: dict[str, Any],
    events: list[dict[str, Any]],
    observability: dict[str, Any],
) -> LoopEvidence:
    promotion = _read_json(project_root / "drafts" / "promotions" / "scene_0001_promotion.json")
    event_names, task_ids = _event_evidence(events)
    current_task = str(run.get("current_task_id") or "")
    return LoopEvidence(
        runtime_is_pi=str(run.get("runtime") or "") == "pi-worker",
        pi_session_seen=_pi_session_seen(observability),
        provider_request_seen="worker.runner.provider.request.started" in event_names,
        candidate_reviewed_and_promoted=_promotion_passed(project_root, promotion),
        promoted_draft_exists=(project_root / "drafts" / "scenes" / "scene_0001.md").is_file(),
        state_applied=(project_root / "characters" / "state_patches" / "scene_0001_state_apply.json").is_file(),
        continuity_applied=(project_root / "plot" / "ledger_deltas" / "scene_0001_apply.json").is_file(),
        next_scene_claimed="scene_0002" in current_task or any("scene_0002" in task_id for task_id in task_ids),
    )


def collect_full_work_evidence(
    project_root: Path,
    run: dict[str, Any],
    events: list[dict[str, Any]],
    observability: dict[str, Any],
    reader: dict[str, Any],
    delivery: dict[str, Any],
    acceptance: FullWorkAcceptance,
) -> FullWorkEvidence:
    """Collect black-box delivery evidence without trusting run narration."""

    event_names, _ = _event_evidence(events)
    formal_scenes = tuple(sorted((project_root / "scenes").glob("scene_*.yaml")))
    promoted_scenes = tuple(sorted((project_root / "drafts" / "scenes").glob("scene_*.md")))
    return FullWorkEvidence(
        runtime_is_pi=str(run.get("runtime") or "") == "pi-worker",
        pi_session_seen=_pi_session_seen(observability),
        provider_request_seen="worker.runner.provider.request.started" in event_names,
        formal_chapter_count=len(tuple((project_root / "outline" / "chapters").glob("chapter_*.yaml"))),
        formal_scene_count=len(formal_scenes),
        promoted_scene_count=len(promoted_scenes),
        passed_promotion_count=sum(
            _promotion_passed(project_root, _read_json(path))
            for path in (project_root / "drafts" / "promotions").glob("scene_*_promotion.json")
        ),
        reviewed_scene_count=len(tuple((project_root / "reviews" / "agent").glob("scene_*_scene_review.json"))),
        state_applied_count=len(
            tuple((project_root / "characters" / "state_patches").glob("scene_*_state_apply.json"))
        ),
        continuity_applied_count=len(
            tuple((project_root / "plot" / "ledger_deltas").glob("scene_*_apply.json"))
        ),
        total_chinese_content_chars=int(reader.get("total_chinese_content_chars") or 0),
        delivery_file_count=len(delivery.get("files") or []),
        delivery_status=str(delivery.get("status") or ""),
        run_status=str(run.get("status") or ""),
        acceptance=acceptance,
    )


def _event_evidence(events: list[dict[str, Any]]) -> tuple[set[str], list[str]]:
    names = {str(item.get("event") or "") for item in events}
    task_ids: list[str] = []
    for item in events:
        data = item.get("data")
        if isinstance(data, dict):
            task_ids.append(str(data.get("task_id") or ""))
    return names, task_ids


def _pi_session_seen(observability: dict[str, Any]) -> bool:
    sessions = observability.get("sessions")
    if not isinstance(sessions, list):
        return False
    return any(
        str(item.get("runtime") or "") == "pi-worker"
        for item in sessions
        if isinstance(item, dict)
    )


def _promotion_passed(project_root: Path, promotion: dict[str, Any]) -> bool:
    review = promotion.get("candidate_review")
    generation = promotion.get("candidate_generation")
    return (
        isinstance(review, dict)
        and isinstance(generation, dict)
        and str(review.get("status") or "") == "pass"
        and str(generation.get("status") or "") == "pass"
        and (project_root / "reviews" / "agent" / "scene_0001_scene_review.json").is_file()
    )


def configure_pi(api: StudioApi) -> str:
    catalog = api.get("/model-connections/pi-worker/catalog")
    selected = str(catalog.get("selected_model") or "")
    available = [
        str(model.get("qualified_id") or "")
        for provider in catalog.get("providers", [])
        if isinstance(provider, dict) and provider.get("connected")
        for model in provider.get("models", [])
        if isinstance(model, dict) and model.get("qualified_id")
    ]
    model = selected if selected in available else (available[0] if available else "")
    if not model:
        raise RuntimeError("Pi Worker has no connected model; connect a provider in Settings first")
    if selected != model:
        api.send("PUT", "/model-connections/pi-worker/model", {"model": model, "role": "worker"})
    return model


def create_acceptance_project(
    api: StudioApi,
    parent: Path,
    title: str,
    *,
    target_length: int = 6000,
    target_chapters: int = 1,
    target_scenes: int = 2,
) -> Path:
    project = api.send(
        "POST",
        "/projects/create",
        {
            "parent_directory": str(parent),
            "title": title,
            "folder_name": title,
            "work_type": "novel",
            "target_length": target_length,
            "target_chapters": target_chapters,
            "target_scenes": target_scenes,
            "genre": "近未来科幻",
            "premise": "一名轨道维修员收到来自已经失联空间站的求救信号，在救人、保住返航燃料和查明事故真相之间作出会改变两个家庭命运的选择。",
        },
    ).get("project")
    if not isinstance(project, dict) or not project.get("path"):
        raise RuntimeError("project creation did not return a project path")
    root = Path(str(project["path"])).resolve()
    api.send(
        "POST",
        "/projects/directions",
        {
            "project_root": str(root),
            "message": (
                f"写成完整的近未来科幻小说，共 {target_chapters} 章、{target_scenes} 个场景，"
                f"正式正文不少于 {target_length} 个中文内容字符。故事必须逐章推进求救信号、燃料困境、"
                "事故真相与家庭代价；人物行为符合轨道维修职业逻辑，场景之间存在明确因果和情绪承接，"
                "结局完成核心选择并兑现主要读者承诺。"
            ),
        },
    )
    return root


def authorize_and_start(api: StudioApi, project_root: Path) -> dict[str, Any]:
    status = api.get("/autopilot/status", project_root=str(project_root))
    policy = status.get("policy") if isinstance(status.get("policy"), dict) else {}
    policy.update(
        {
            "mode": "full_auto",
            "delegated_routes": [
                "longform-planning", "style-engineering", "character-and-world-assets",
                "scene-development", "review-and-audit", "export-and-release",
            ],
            "delegated_decisions": DELEGATED_DECISIONS,
            "release_policy": "delegated",
        }
    )
    policy["limits"] = {
        **(policy.get("limits") if isinstance(policy.get("limits"), dict) else {}),
        "max_tasks": 500,
        "max_runtime_hours": 24,
        "max_consecutive_revisions": 6,
        "max_failures_per_task": 2,
        "max_cost": 100,
    }
    api.send("PUT", "/autopilot/policy", {"project_root": str(project_root), "policy": policy})
    result = api.send(
        "POST",
        "/autopilot/start",
        {"project_root": str(project_root), "runtime": "pi-worker", "authorized": True},
    )
    run = result.get("run")
    if not isinstance(run, dict):
        raise RuntimeError("autopilot start did not return a run")
    return run


def monitor(
    api: StudioApi,
    project_root: Path,
    run_id: str,
    *,
    timeout_seconds: int,
    poll_seconds: float,
    stall_seconds: int,
    full_work_acceptance: FullWorkAcceptance | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]], LoopEvidence | FullWorkEvidence]:
    started = time.monotonic()
    changed = started
    previous_signature = ""
    latest_run: dict[str, Any] = {}
    latest_events: list[dict[str, Any]] = []
    evidence: LoopEvidence | FullWorkEvidence = LoopEvidence(
        False, False, False, False, False, False, False, False
    )
    while time.monotonic() - started < timeout_seconds:
        latest_run = api.get("/autopilot/status", project_root=str(project_root)).get("run") or {}
        latest_events = api.get(f"/autopilot/runs/{run_id}/events", after=0, limit=2000).get("items") or []
        observability = api.get("/agent-observability", project_root=str(project_root))
        if full_work_acceptance is None:
            evidence = collect_evidence(project_root, latest_run, latest_events, observability)
        else:
            reader = api.get("/reader/manifest", project_root=str(project_root))
            delivery = api.get("/project/delivery", project_root=str(project_root))
            evidence = collect_full_work_evidence(
                project_root,
                latest_run,
                latest_events,
                observability,
                reader,
                delivery,
                full_work_acceptance,
            )
        signature = json.dumps(
            {
                "status": latest_run.get("status"),
                "route": latest_run.get("current_route"),
                "task": latest_run.get("current_task_id"),
                "completed": latest_run.get("tasks_completed"),
                "events": latest_events[-1].get("sequence") if latest_events else 0,
                "evidence": asdict(evidence),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
        if signature != previous_signature:
            changed = time.monotonic()
            previous_signature = signature
            print(signature, flush=True)
        if evidence.complete:
            return latest_run, latest_events, evidence
        status = str(latest_run.get("status") or "")
        if status in TERMINAL_RUN_STATUSES:
            raise RuntimeError(f"autopilot stopped before continuous-loop acceptance: {status}: {latest_run.get('last_error') or latest_run.get('stop_reason')}")
        if time.monotonic() - changed >= stall_seconds:
            raise RuntimeError(f"autopilot made no observable progress for {stall_seconds} seconds")
        time.sleep(max(0.5, poll_seconds))
    raise TimeoutError(f"continuous Pi E2E exceeded {timeout_seconds} seconds")


def write_report(
    destination: Path,
    *,
    project_root: Path,
    model: str,
    run: dict[str, Any],
    events: list[dict[str, Any]],
    evidence: LoopEvidence | FullWorkEvidence,
) -> Path:
    destination.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = destination / f"pi-continuous-e2e-{stamp}.json"
    payload = {
        "schema": "arcvellum/pi-continuous-e2e/v1",
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "project_root": str(project_root),
        "model": model,
        "run": {key: run.get(key) for key in ("run_id", "runtime", "status", "current_route", "current_task_id", "tasks_completed", "failures", "stop_reason")},
        "evidence": asdict(evidence),
        "event_timeline": [
            {
                "sequence": item.get("sequence"),
                "event": item.get("event"),
                "at": item.get("at"),
                "task_id": (item.get("data") or {}).get("task_id") if isinstance(item.get("data"), dict) else "",
            }
            for item in events
        ],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8798")
    parser.add_argument("--projects-root", type=Path, required=True)
    parser.add_argument("--title", default=f"Pi连续闭环验收-{datetime.now().strftime('%Y%m%d-%H%M%S')}")
    parser.add_argument("--acceptance", choices=("first-loop", "full-work"), default="first-loop")
    parser.add_argument("--target-length", type=int, default=6000)
    parser.add_argument("--target-chapters", type=int, default=1)
    parser.add_argument("--target-scenes", type=int, default=2)
    parser.add_argument("--timeout", type=int, default=7200)
    parser.add_argument("--poll", type=float, default=2.0)
    parser.add_argument("--stall", type=int, default=600)
    parser.add_argument("--report-root", type=Path, default=Path("build/verification/pi-e2e"))
    args = parser.parse_args(argv)
    api = StudioApi(args.base_url)
    model = configure_pi(api)
    project = create_acceptance_project(
        api,
        args.projects_root.resolve(),
        args.title,
        target_length=max(1000, args.target_length),
        target_chapters=max(1, args.target_chapters),
        target_scenes=max(1, args.target_scenes),
    )
    run = authorize_and_start(api, project)
    full_work_acceptance = (
        FullWorkAcceptance(
            target_chapters=max(1, args.target_chapters),
            target_scenes=max(1, args.target_scenes),
            target_chinese_chars=max(1000, args.target_length),
        )
        if args.acceptance == "full-work"
        else None
    )
    final_run, events, evidence = monitor(
        api,
        project,
        str(run["run_id"]),
        timeout_seconds=args.timeout,
        poll_seconds=args.poll,
        stall_seconds=args.stall,
        full_work_acceptance=full_work_acceptance,
    )
    if args.acceptance == "first-loop":
        api.send("POST", f"/autopilot/runs/{run['run_id']}/pause", {"reason": "pi-continuous-e2e-complete"})
    report = write_report(args.report_root, project_root=project, model=model, run=final_run, events=events, evidence=evidence)
    print(json.dumps({"ok": True, "project_root": str(project), "report": str(report)}, ensure_ascii=False))
    return 0


__all__ = [
    "FullWorkAcceptance",
    "FullWorkEvidence",
    "LoopEvidence",
    "StudioApi",
    "collect_evidence",
    "collect_full_work_evidence",
    "main",
]
