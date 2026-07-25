"""Create registered formal assets through audited owner transactions."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import threading

from .contracts import AssetRecord, OwnerAssetCreation, SemanticReview
from .impact import build_asset_impact
from .loader import AssetLoader
from .registry import AssetViewRegistry
from .revisions import AssetRevisionService, content_revision
from .staleness import build_formal_stale_propagation
from .validation import validate_asset_creation


EMPTY_CONTENT_REVISION = content_revision("")


class AssetCreationConflictError(RuntimeError):
    pass


class AssetCreationPreviewStaleError(RuntimeError):
    pass


class OwnerCreationService:
    def __init__(
        self,
        registry: AssetViewRegistry,
        loader: AssetLoader,
        revisions: AssetRevisionService | None = None,
    ):
        self.registry = registry
        self.loader = loader
        self.revisions = revisions
        self._lock = threading.RLock()

    def options(self, project_root: Path) -> dict[str, object]:
        root = self.loader.project_root(project_root)
        items: list[dict[str, object]] = []
        for definition in self.registry.definitions():
            if not definition.supports_create:
                continue
            fixed_id = definition.fixed_id
            existing = bool(
                fixed_id
                and self.loader.resolve_path(
                    root,
                    self.registry.asset_id(definition, fixed_id),
                ).is_file()
            )
            items.append(
                {
                    "asset_type": definition.asset_type,
                    "schema_id": definition.schema_id,
                    "editor_kind": definition.editor_kind.value,
                    "id_field": definition.id_field,
                    "fixed_id": fixed_id,
                    "writable_fields": list(definition.writable_fields),
                    "field_definitions": [
                        field.as_dict() for field in definition.field_definitions
                    ],
                    "template": creation_template(definition.asset_type),
                    "available": not existing,
                    "unavailable_reason": "正式资产已存在" if existing else "",
                }
            )
        return {
            "schema": "arcvellum/archive-creation-options/v1",
            "items": items,
        }

    def preview(
        self,
        project_root: Path,
        creation: OwnerAssetCreation,
    ) -> dict[str, object]:
        root = self.loader.project_root(project_root)
        definition, local_id = self.registry.parse_asset_id(creation.asset_id)
        self._validate_creation(definition.asset_type, creation)
        target = self.loader.resolve_path(root, creation.asset_id)
        validation = validate_asset_creation(root, definition, local_id, creation.content)
        target_absent = not target.exists()
        impact = build_asset_impact(
            root,
            AssetRecord(
                asset_id=creation.asset_id,
                asset_type=definition.asset_type,
                local_id=local_id,
                relative_path=target.relative_to(root).as_posix(),
                revision=EMPTY_CONTENT_REVISION,
                title=local_id,
                content="",
                media_type=_media_type(target),
            ),
            creation.content,
        )
        digest = _preview_digest(creation, validation.as_dict(), impact)
        return {
            "schema": "arcvellum/owner-asset-creation-preview/v1",
            "transaction": creation.as_dict(),
            "asset": {
                "asset_id": creation.asset_id,
                "asset_type": definition.asset_type,
                "target_state": "absent" if target_absent else "exists",
            },
            "validation": validation.as_dict(),
            "impact": impact,
            "preview_digest": digest,
            "committable": (
                definition.supports_create
                and target_absent
                and validation.valid
                and creation.semantic_review == SemanticReview.WAIVED
            ),
        }

    def create(
        self,
        project_root: Path,
        creation: OwnerAssetCreation,
        *,
        preview_digest: str,
    ) -> dict[str, object]:
        if creation.semantic_review != SemanticReview.WAIVED:
            raise ValueError("semantic review is required before a formal asset can be created")
        if len(creation.reason) < 6:
            raise ValueError("asset creation reason must explain the author decision")
        with self._lock:
            preview = self.preview(project_root, creation)
            if str(preview["preview_digest"]) != preview_digest:
                raise AssetCreationPreviewStaleError(
                    "asset creation preview no longer matches the requested content"
                )
            if preview["asset"]["target_state"] != "absent":
                raise AssetCreationConflictError("formal asset already exists")
            if not preview["committable"]:
                raise ValueError("asset creation failed deterministic validation")
            return self._create_locked(project_root.resolve(), creation, preview)

    def _create_locked(
        self,
        root: Path,
        creation: OwnerAssetCreation,
        preview: dict[str, object],
    ) -> dict[str, object]:
        target = self.loader.resolve_path(root, creation.asset_id)
        if target.exists():
            raise AssetCreationConflictError("formal asset already exists")
        transaction_root = root / "workflow" / "archive" / "transactions"
        transaction_root.mkdir(parents=True, exist_ok=True)
        final_dir = transaction_root / creation.transaction_id
        staging_dir = transaction_root / f".{creation.transaction_id}.tmp"
        if final_dir.exists() or staging_dir.exists():
            raise ValueError("owner creation transaction id already exists")
        target.parent.mkdir(parents=True, exist_ok=True)
        staging_dir.mkdir()
        suffix = target.suffix or ".txt"
        before = staging_dir / f"before{suffix}"
        after = staging_dir / f"after{suffix}"
        before.write_text("", encoding="utf-8")
        after.write_text(creation.content, encoding="utf-8")
        _write_json(staging_dir / "transaction.json", creation.as_dict())
        new_revision = content_revision(creation.content)
        receipt = {
            "schema": "arcvellum/mutation-receipt/v1",
            "operation": "create",
            "transaction_id": creation.transaction_id,
            "asset_id": creation.asset_id,
            "asset_type": creation.asset_type,
            "authority": "owner",
            "semantic_review": creation.semantic_review.value,
            "base_revision": EMPTY_CONTENT_REVISION,
            "new_revision": new_revision,
            "reason": creation.reason,
            "impact": preview["impact"],
            "stale_propagation": {
                "schema": "arcvellum/archive-stale-propagation/v1",
                "status": "pending",
            },
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        _write_json(staging_dir / "receipt.json", receipt)
        try:
            with target.open("x", encoding="utf-8", newline="") as stream:
                stream.write(creation.content)
            staging_dir.replace(final_dir)
        except FileExistsError as exc:
            shutil.rmtree(staging_dir, ignore_errors=True)
            raise AssetCreationConflictError("formal asset already exists") from exc
        except Exception:
            target.unlink(missing_ok=True)
            shutil.rmtree(staging_dir, ignore_errors=True)
            raise
        receipt.update(
            {
                "receipt_path": (final_dir / "receipt.json").relative_to(root).as_posix(),
                "transaction_path": (final_dir / "transaction.json").relative_to(root).as_posix(),
                "before_snapshot": (final_dir / f"before{suffix}").relative_to(root).as_posix(),
                "after_snapshot": (final_dir / f"after{suffix}").relative_to(root).as_posix(),
                "stale_propagation": build_formal_stale_propagation(
                    root,
                    target.relative_to(root).as_posix(),
                ),
            }
        )
        _write_json(final_dir / "receipt.json", receipt)
        self._record_history_index(root, receipt)
        return receipt

    @staticmethod
    def _validate_creation(asset_type: str, creation: OwnerAssetCreation) -> None:
        if creation.authority != "owner":
            raise ValueError("asset creation authority must be owner")
        if creation.asset_type != asset_type:
            raise ValueError("asset creation asset_type does not match asset_id")

    def _record_history_index(self, root: Path, receipt: dict[str, object]) -> None:
        if self.revisions is None:
            receipt["history_index"] = {"status": "not-configured"}
        else:
            try:
                self.revisions.index_receipt(root, receipt)
            except (OSError, RuntimeError, ValueError) as exc:
                receipt["history_index"] = {
                    "status": "rebuild-required",
                    "message": str(exc),
                }
            else:
                receipt["history_index"] = {"status": "indexed"}
        _write_json(root / str(receipt["receipt_path"]), receipt)


def creation_template(asset_type: str) -> str:
    try:
        return _CREATION_TEMPLATES[asset_type]
    except KeyError as exc:
        raise ValueError(f"no controlled creation template for asset type: {asset_type}") from exc


def materialize_creation_template(template: str, local_id: str) -> str:
    return template.replace("__ASSET_ID__", local_id)


def _preview_digest(
    creation: OwnerAssetCreation,
    validation: dict[str, object],
    impact: dict[str, object],
) -> str:
    payload = {
        "asset_id": creation.asset_id,
        "asset_type": creation.asset_type,
        "content_revision": content_revision(creation.content),
        "semantic_review": creation.semantic_review.value,
        "reason": creation.reason,
        "expected_impacts": list(creation.expected_impacts),
        "validation": validation,
        "impact": impact,
    }
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return f"sha256:{hashlib.sha256(encoded.encode('utf-8')).hexdigest()}"


def _media_type(path: Path) -> str:
    return "application/json" if path.suffix.lower() == ".json" else "application/yaml"


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


_CREATION_TEMPLATES = {
    "character": """character_id: "__ASSET_ID__"
name: ""
aliases: []
role: ""
importance: secondary
background_story:
  summary: ""
  formative_events: []
  behavior_influences: []
  reveal_policy: implicit_only
bdi:
  belief: []
  desire: []
  intention: []
psychology:
  fear: []
  secret: []
  wound: ""
  mask: ""
  moral_line: ""
relationships: []
state:
  location: ""
  health: ""
  resources: []
  known_facts: []
  unknown_facts: []
""",
    "scene": """scene_id: "__ASSET_ID__"
chapter_id: ""
status: planned
word_count_target: 0
word_count_min: 0
word_count_max: 0
time:
  story_time: ""
  timeline_order: null
location: ""
participants: []
participant_refs: []
scene_goal: ""
conflict:
  external: ""
  internal: ""
reader_experience:
  reader_question: ""
  promised_reward: ""
  withheld_information: []
  payoff_or_delay: ""
narrative_rhythm:
  rhythm_role: mixed
  pace: balanced
  density: medium
  scene_function: []
  scene_turn: ""
  reader_effect: ""
scene_bridge:
  incoming_from_previous: []
  outgoing_hooks: []
output_state:
  new_facts: []
  character_changes: []
  relationship_changes: []
  foreshadowing_changes: []
  next_hooks: []
""",
    "world-rule": "rules: []\nconstraints: []\nopen_questions: []\n",
    "location-catalog": "locations: []\n",
    "organization-catalog": "organizations: []\n",
    "promise-ledger": '{\n  "promises": []\n}\n',
    "reader-question-ledger": '{\n  "reader_questions": []\n}\n',
}
