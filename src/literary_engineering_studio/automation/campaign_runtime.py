"""Runtime projections that connect Campaign contracts to Autopilot evidence.

This module owns no thread, retry loop, or formal project write.  It turns the
current project truth into deterministic progress/checkpoint evidence for the
existing :class:`ClaimedRunLoop`.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
from pathlib import Path
import re
from typing import Any, Protocol

from literary_engineering_studio_engine.foundation.display_cleaner import (
    scalar_from_yaml_text,
)
from literary_engineering_studio_engine.foundation.draft_text import (
    count_delivery_chinese_content_chars,
)

from ..orchestration import (
    CampaignPolicy,
    CampaignState,
    CampaignStepDecision,
    ChapterCheckpoint,
    ProgressFingerprint,
    ProgressFingerprintInput,
    campaign_step_allowed,
    campaign_violations,
    checkpoint_due,
    checkpoint_violations,
    progress_fingerprint,
    progress_input_violations,
)
from .support import PROGRESS_EXCLUDED_PARTS, PROGRESS_ROOTS


_SCENE_ID = re.compile(r"scene_\d+")


@dataclass(frozen=True)
class FormalProgressEvidence:
    """Content-addressed evidence for one formal project scope."""

    progress: ProgressFingerprint
    base_project_fingerprint: str
    promoted_hanzi: int
    artifact_count: int


class CampaignEventStore(Protocol):
    """Narrow persistence surface used by the runtime collaborator."""

    def append_autopilot_event(
        self, run_id: str, event: str, data: dict[str, Any]
    ) -> dict[str, Any]: ...

    def latest_autopilot_event(
        self, run_id: str, event: str
    ) -> dict[str, Any] | None: ...


class CampaignRuntimeCoordinator:
    """Project one existing Autopilot run into Campaign/checkpoint contracts."""

    def __init__(
        self,
        store: CampaignEventStore,
        project: Path,
        run_id: str,
        *,
        max_autonomous_steps: int,
        checkpoint_interval_steps: int,
    ) -> None:
        self.store = store
        self.project = project.expanduser().resolve()
        self.run_id = run_id
        self.scope_key = _book_scope_key(self.project)
        self.policy = CampaignPolicy(
            scope_kind="book",
            scope_key=self.scope_key,
            max_autonomous_steps=max(1, int(max_autonomous_steps)),
            checkpoint_interval_steps=max(1, int(checkpoint_interval_steps)),
            pause_on=(),
        )

    def progress_evidence(self) -> FormalProgressEvidence:
        return formal_progress_evidence(
            self.project,
            scope_key=self.scope_key,
        )

    def step_decision(self, run: dict[str, Any]) -> CampaignStepDecision:
        state = self._state(run)
        issues = campaign_violations(state, self.policy)
        if issues:
            return CampaignStepDecision(
                proceed=False,
                reasons=(f"invalid-campaign:{issues[0].code}",),
            )
        return campaign_step_allowed(state, self.policy)

    def ensure_baseline(self, run: dict[str, Any]) -> dict[str, Any]:
        current = self.latest_checkpoint()
        if current is not None:
            return current
        evidence = self.progress_evidence()
        return self.store.append_autopilot_event(
            self.run_id,
            "campaign.checkpoint.created",
            build_checkpoint_payload(
                self.project,
                run_id=self.run_id,
                route=str(run.get("current_route") or ""),
                task_id=str(run.get("current_task_id") or ""),
                completed_steps=int(run.get("tasks_completed") or 0),
                evidence=evidence,
                created_at=_required_time(run),
            ),
        )

    def checkpoint_after_progress(
        self,
        run: dict[str, Any],
        *,
        route: str,
        task_id: str,
        evidence: FormalProgressEvidence,
        created_at: str,
    ) -> dict[str, Any] | None:
        state = self._state(run)
        if campaign_violations(state, self.policy) or not checkpoint_due(
            state, self.policy
        ):
            return None
        return self.store.append_autopilot_event(
            self.run_id,
            "campaign.checkpoint.created",
            build_checkpoint_payload(
                self.project,
                run_id=self.run_id,
                route=route,
                task_id=task_id,
                completed_steps=state.completed_steps,
                evidence=evidence,
                created_at=created_at,
            ),
        )

    def restore_allowed(self) -> tuple[bool, str]:
        checkpoint = self.latest_checkpoint()
        if checkpoint is None:
            return False, "missing-checkpoint"
        evidence = self.progress_evidence()
        if not checkpoint_matches_evidence(checkpoint["data"], evidence):
            return False, "checkpoint-project-drift"
        return True, "checkpoint-matched"

    def latest_checkpoint(self) -> dict[str, Any] | None:
        return self.store.latest_autopilot_event(
            self.run_id,
            "campaign.checkpoint.created",
        )

    def _state(self, run: dict[str, Any]) -> CampaignState:
        checkpoint = self.latest_checkpoint()
        checkpoint_data = checkpoint.get("data") if checkpoint else {}
        return CampaignState(
            scope_key=self.scope_key,
            completed_steps=int(run.get("tasks_completed") or 0),
            last_checkpoint_step=int(
                (checkpoint_data or {}).get("completed_steps") or 0
            ),
        )


def formal_progress_evidence(
    project: Path,
    *,
    scope_key: str,
) -> FormalProgressEvidence:
    """Hash formal artifact content, excluding Studio/runtime projections."""

    root = project.expanduser().resolve()
    artifacts = tuple(_formal_artifact_digests(root))
    promoted_hanzi = _promoted_hanzi(root)
    inputs = ProgressFingerprintInput(
        scope_key=scope_key,
        formal_artifact_digests=artifacts,
        promoted_hanzi=promoted_hanzi,
    )
    violations = progress_input_violations(inputs)
    if violations:
        raise ValueError(violations[0].message)
    base_digest = sha256(
        "\n".join(f"{path}:{digest}" for path, digest in artifacts).encode(
            "utf-8"
        )
    ).hexdigest()
    return FormalProgressEvidence(
        progress=progress_fingerprint(inputs),
        base_project_fingerprint=base_digest,
        promoted_hanzi=promoted_hanzi,
        artifact_count=len(artifacts),
    )


def build_checkpoint_payload(
    project: Path,
    *,
    run_id: str,
    route: str,
    task_id: str,
    completed_steps: int,
    evidence: FormalProgressEvidence,
    created_at: str,
) -> dict[str, Any]:
    """Build a durable event payload; add chapter evidence only when proven."""

    payload: dict[str, Any] = {
        "schema": "arcvellum/campaign-checkpoint/v1",
        "checkpoint_id": _checkpoint_id(
            run_id,
            completed_steps,
            evidence.progress.fingerprint,
        ),
        "scope_kind": "book",
        "scope_key": evidence.progress.scope_key,
        "completed_steps": completed_steps,
        "route": route,
        "last_task_id": task_id,
        "base_project_fingerprint": evidence.base_project_fingerprint,
        "progress_fingerprint": evidence.progress.fingerprint,
        "promoted_hanzi": evidence.promoted_hanzi,
        "artifact_count": evidence.artifact_count,
        "created_at": created_at,
    }
    chapter = _chapter_checkpoint(
        project.expanduser().resolve(),
        payload,
        route=route,
        task_id=task_id,
    )
    if chapter is not None:
        payload["chapter_checkpoint"] = asdict(chapter)
    return payload


def checkpoint_matches_evidence(
    payload: dict[str, Any],
    evidence: FormalProgressEvidence,
) -> bool:
    """Return whether a persisted safe point still identifies current truth."""

    return (
        str(payload.get("scope_key") or "") == evidence.progress.scope_key
        and str(payload.get("base_project_fingerprint") or "")
        == evidence.base_project_fingerprint
        and str(payload.get("progress_fingerprint") or "")
        == evidence.progress.fingerprint
    )


def _formal_artifact_digests(root: Path):
    seen: set[str] = set()
    for relative in PROGRESS_ROOTS:
        target = root / relative
        if target.is_file():
            candidates = (target,)
        elif target.is_dir():
            candidates = sorted(path for path in target.rglob("*") if path.is_file())
        else:
            continue
        for path in candidates:
            relative_path = path.relative_to(root)
            if any(part.lower() in PROGRESS_EXCLUDED_PARTS for part in relative_path.parts):
                continue
            normalized = relative_path.as_posix()
            if normalized in seen:
                continue
            seen.add(normalized)
            try:
                digest = sha256(path.read_bytes()).hexdigest()
            except OSError as exc:
                raise RuntimeError(
                    f"cannot read formal progress artifact: {normalized}"
                ) from exc
            yield normalized, digest


def _promoted_hanzi(root: Path) -> int:
    total = 0
    drafts = root / "drafts" / "scenes"
    if not drafts.is_dir():
        return 0
    for path in sorted(drafts.glob("scene_*.md")):
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            raise RuntimeError(
                f"cannot read promoted scene draft: {path.relative_to(root).as_posix()}"
            ) from exc
        total += count_delivery_chinese_content_chars(text)
    return total


def _chapter_checkpoint(
    root: Path,
    payload: dict[str, Any],
    *,
    route: str,
    task_id: str,
) -> ChapterCheckpoint | None:
    if route != "scene-development":
        return None
    match = _SCENE_ID.search(task_id)
    if match is None:
        return None
    scene_id = match.group(0)
    scene_path = root / "scenes" / f"{scene_id}.yaml"
    try:
        scene_text = scene_path.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return None
    if scalar_from_yaml_text(scene_text, "scene_id") != scene_id:
        return None
    chapter_id = scalar_from_yaml_text(scene_text, "chapter_id")
    if not chapter_id:
        return None
    checkpoint = ChapterCheckpoint(
        checkpoint_id=str(payload["checkpoint_id"]),
        chapter_id=chapter_id,
        base_project_fingerprint=str(payload["base_project_fingerprint"]),
        progress_fingerprint=str(payload["progress_fingerprint"]),
        last_task_id=task_id,
        promoted_scene_ids=_promoted_scene_ids(root),
        pending_decision_ids=(),
        created_at=str(payload["created_at"]),
    )
    return None if checkpoint_violations(checkpoint) else checkpoint


def _promoted_scene_ids(root: Path) -> tuple[str, ...]:
    drafts = root / "drafts" / "scenes"
    if not drafts.is_dir():
        return ()
    return tuple(path.stem for path in sorted(drafts.glob("scene_*.md")))


def _checkpoint_id(run_id: str, completed_steps: int, fingerprint: str) -> str:
    identity = f"{run_id}:{completed_steps}:{fingerprint}"
    return f"checkpoint-{sha256(identity.encode('utf-8')).hexdigest()[:16]}"


def _book_scope_key(project: Path) -> str:
    digest = sha256(str(project).casefold().encode("utf-8")).hexdigest()[:16]
    return f"book:{digest}"


def _required_time(run: dict[str, Any]) -> str:
    for key in ("updated_at", "started_at", "created_at"):
        value = str(run.get(key) or "").strip()
        if value:
            return value
    raise ValueError("campaign run must provide a persisted timestamp")
    campaign_step_allowed,
    campaign_violations,
    checkpoint_due,
