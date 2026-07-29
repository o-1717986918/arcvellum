"""Load one fully authorized active plan for formal Worker task binding."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Callable

from .codec import parse_compiled_task_graph, parse_creative_execution_plan
from .contracts import CompiledTaskGraph, CreativeExecutionPlan
from .persistence import read_verified_revision_payloads, verify_persisted_revision
from .plan_index import CreativePlanIndex


ACTIVE_PLAN_SCHEMA = "arcvellum/active-creative-plan/v1"


@dataclass(frozen=True)
class ActiveScenePlan:
    plan: CreativeExecutionPlan
    graph: CompiledTaskGraph
    revision_digest: str
    authorization_digest: str
    project_fingerprint: str


class ActivePlanLoader:
    def __init__(
        self,
        store: CreativePlanIndex,
        *,
        fingerprint_provider: Callable[[Path], str],
    ):
        self.store = store
        self.fingerprint_provider = fingerprint_provider

    def load(self, project_root: Path) -> ActiveScenePlan | None:
        root = project_root.expanduser().resolve()
        projection_path = root / "workflow" / "orchestration" / "active_plan.json"
        if not projection_path.is_file():
            return None
        projection = _read_projection(projection_path)
        plan_id = projection["plan_id"]
        revision = projection["revision"]
        plan_record = self.store.read_creative_plan(plan_id)
        revision_record = self.store.read_creative_plan_revision(plan_id, revision)
        _validate_index_state(root, plan_record, revision_record, projection)
        verified_digest = verify_persisted_revision(root, revision_record)
        if verified_digest != projection["revision_digest"]:
            raise RuntimeError("active creative plan revision digest is inconsistent")
        authorization = _authorization(revision_record)
        if authorization["digest"] != projection["authorization_digest"]:
            raise RuntimeError("active creative plan authorization digest is inconsistent")
        current_fingerprint = str(self.fingerprint_provider(root) or "").strip()
        if not current_fingerprint:
            raise RuntimeError("active creative plan fingerprint provider returned no value")
        if current_fingerprint != projection["base_project_fingerprint"]:
            raise RuntimeError("active creative plan is stale for the current project")
        payloads = read_verified_revision_payloads(root, revision_record)
        plan = parse_creative_execution_plan(payloads["normalized"])
        graph = parse_compiled_task_graph(payloads["compiled"])
        _validate_contract_identity(plan, graph, projection)
        return ActiveScenePlan(
            plan=plan,
            graph=graph,
            revision_digest=verified_digest,
            authorization_digest=authorization["digest"],
            project_fingerprint=current_fingerprint,
        )


def _read_projection(path: Path) -> dict[str, object]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        raise RuntimeError("active creative plan projection is unreadable") from exc
    required = {
        "schema",
        "plan_id",
        "revision",
        "revision_digest",
        "authorization_digest",
        "base_project_fingerprint",
    }
    if not isinstance(payload, dict) or set(payload) != required:
        raise RuntimeError("active creative plan projection has an invalid contract")
    if payload.get("schema") != ACTIVE_PLAN_SCHEMA:
        raise RuntimeError("active creative plan projection schema is unsupported")
    if not isinstance(payload.get("revision"), int) or int(payload["revision"]) < 1:
        raise RuntimeError("active creative plan projection revision is invalid")
    for key in (
        "plan_id",
        "revision_digest",
        "authorization_digest",
        "base_project_fingerprint",
    ):
        if not isinstance(payload.get(key), str) or not str(payload[key]).strip():
            raise RuntimeError(f"active creative plan projection {key} is invalid")
    return payload


def _validate_index_state(
    root: Path,
    plan: dict[str, object],
    revision: dict[str, object],
    projection: dict[str, object],
) -> None:
    expected_project = str(root).replace("\\", "/").rstrip("/").casefold()
    observed_project = str(plan.get("project_root") or "").replace("\\", "/").rstrip("/").casefold()
    if observed_project != expected_project:
        raise RuntimeError("active creative plan belongs to another project")
    if str(plan.get("status") or "") != "active":
        raise RuntimeError("active creative plan projection points to a non-active plan")
    if int(plan.get("active_revision") or 0) != int(projection["revision"]):
        raise RuntimeError("active creative plan projection and SQLite revision differ")
    if str(plan.get("base_project_fingerprint") or "") != projection["base_project_fingerprint"]:
        raise RuntimeError("active creative plan projection and SQLite fingerprint differ")
    if str(revision.get("artifact_state") or "") != "ready":
        raise RuntimeError("active creative plan revision artifacts are not ready")
    if str(revision.get("digest") or "") != projection["revision_digest"]:
        raise RuntimeError("active creative plan projection and revision digest differ")
    _authorization(revision)


def _authorization(revision: dict[str, object]) -> dict[str, str]:
    review = revision.get("review")
    if not isinstance(review, dict):
        raise RuntimeError("active creative plan lacks review metadata")
    authorization = review.get("authorization")
    if (
        review.get("activation_eligible") is not True
        or review.get("lifecycle") != "assisted_authorized"
        or not isinstance(authorization, dict)
    ):
        raise RuntimeError("creative plan revision is not assisted-authorized")
    result = {
        key: str(authorization.get(key) or "").strip()
        for key in (
            "authorized_by",
            "reason",
            "revision_digest",
            "authorized_at",
            "digest",
        )
    }
    if any(not value for value in result.values()):
        raise RuntimeError("creative plan assisted authorization is incomplete")
    if result["revision_digest"] != str(revision.get("digest") or ""):
        raise RuntimeError("creative plan authorization belongs to another revision")
    rendered = json.dumps(
        {
            key: result[key]
            for key in (
                "authorized_by",
                "reason",
                "revision_digest",
                "authorized_at",
            )
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    if hashlib.sha256(rendered.encode("utf-8")).hexdigest() != result["digest"]:
        raise RuntimeError("creative plan assisted authorization digest is invalid")
    return result


def _validate_contract_identity(
    plan: CreativeExecutionPlan,
    graph: CompiledTaskGraph,
    projection: dict[str, object],
) -> None:
    identity = (
        plan.plan_id,
        plan.revision,
        plan.base_project_fingerprint,
    )
    expected = (
        str(projection["plan_id"]),
        int(projection["revision"]),
        str(projection["base_project_fingerprint"]),
    )
    graph_identity = (
        graph.plan_id,
        graph.plan_revision,
        graph.base_project_fingerprint,
    )
    if identity != expected or graph_identity != expected:
        raise RuntimeError("active creative plan audit contracts have inconsistent identity")
