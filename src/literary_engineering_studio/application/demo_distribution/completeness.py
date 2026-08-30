"""Deterministic readiness audit for a full literary-engineering demo."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

from literary_engineering_studio_engine.public.projections import load_authorized_reader_units


@dataclass(frozen=True)
class DemoCompletenessReport:
    project_root: Path
    checks: tuple[dict[str, Any], ...]

    @property
    def errors(self) -> tuple[str, ...]:
        return tuple(str(item["detail"]) for item in self.checks if item.get("status") == "error")

    @property
    def ready(self) -> bool:
        return not self.errors

    def require_ready(self) -> "DemoCompletenessReport":
        if self.errors:
            raise ValueError("authorized demo project is incomplete: " + "; ".join(self.errors))
        return self

    def to_record(self) -> dict[str, Any]:
        return {
            "schema": "arcvellum/demo-completeness-report/v1",
            "project_root": str(self.project_root),
            "ready": self.ready,
            "checks": list(self.checks),
        }


def audit_demo_project(project_root: Path | str) -> DemoCompletenessReport:
    root = Path(project_root).expanduser().resolve()
    checks: list[dict[str, Any]] = []
    identity = _read_json(root / ".arcvellum-demo.json")
    _audit_source_facilities(root, identity, checks)
    _audit_literary_facilities(root, checks)
    _check(
        checks,
        "single_work_scope",
        str(identity.get("work_id") or "") == "yu-hua-i-am-timid-as-a-mouse",
        "演示范围仅包含《我胆小如鼠》单篇",
        "演示项目 work_id 与指定单篇作品不一致",
    )
    return DemoCompletenessReport(root, tuple(checks))


def _audit_source_facilities(
    root: Path,
    identity: dict[str, Any],
    checks: list[dict[str, Any]],
) -> None:
    _check(
        checks,
        "authorized_identity",
        identity.get("schema") == "arcvellum/authorized-demo-project/v1",
        "授权演示身份与来源摘要完整",
        "缺少有效的授权演示身份文件",
    )
    ingest = root / str(identity.get("source_ingest_manifest") or "")
    ingest_payload = _read_json(ingest)
    evidence = ingest.parent / "evidence_index.json" if ingest_payload else Path()
    _check(
        checks,
        "source_evidence",
        bool(ingest_payload and evidence.is_file() and ingest_payload.get("source_documents")),
        "原文、抽取文本和证据索引可追溯",
        "授权原文导入或证据索引不完整",
    )
    reader_units = load_authorized_reader_units(root)
    _check(
        checks,
        "authorized_reader",
        bool(reader_units),
        f"授权正文可按 {len(reader_units)} 个阅读单元读取",
        "授权正文没有可验证的阅读单元",
    )


def _audit_literary_facilities(root: Path, checks: list[dict[str, Any]]) -> None:
    promotion_types = _promotion_types(root)
    required_assets = {"character", "world", "outline"}
    missing_assets = sorted(required_assets.difference(promotion_types))
    _check(
        checks,
        "formal_assets",
        not missing_assets,
        "人物、世界与情节资产均有正式晋升凭据",
        "缺少正式晋升资产：" + "、".join(missing_assets),
    )
    scenes = [path for path in (root / "scenes").glob("*.yaml") if not path.name.startswith("_")]
    _check(
        checks,
        "scene_inventory",
        len(scenes) >= 3,
        f"已建立 {len(scenes)} 个原作场景索引",
        "原作场景库存不足；至少需要 3 个证据绑定场景以展示完整工程",
    )

    style = _read_json(root / "style" / "active_style_skill.json")
    style_id = str(style.get("style_id") or "")
    source_style = bool(style_id and style_id != "arcvellum-clear-plain-prose")
    _check(
        checks,
        "source_style",
        source_style,
        f"已挂载原作分析文风：{style_id}",
        "仍在使用通用默认文风，尚未挂载基于原文证据学习的文风",
    )
    rhythm = _read_json(root / "plot" / "rhythm_plan.json")
    _check(
        checks,
        "rhythm_plan",
        bool(rhythm.get("entries")),
        "已建立全文叙事节奏与详略计划",
        "缺少可用的全文节奏计划",
    )
    ledgers = (
        _read_json(root / "plot" / "reader_questions" / "ledger.json"),
        _read_json(root / "plot" / "promises" / "ledger.json"),
    )
    _check(
        checks,
        "reader_ledgers",
        all(item for item in ledgers),
        "读者问题与承诺/兑现账本已建立",
        "读者问题或承诺/兑现账本尚未建立",
    )
    obligations = [
        path
        for path in (root / "plot" / "chapter_obligations").glob("*.json")
        if path.name != "chapter_obligations.json"
    ]
    _check(
        checks,
        "chapter_obligations",
        bool(obligations),
        f"已建立 {len(obligations)} 份章节义务",
        "缺少章节义务与读者体验契约",
    )


def _promotion_types(root: Path) -> set[str]:
    result: set[str] = set()
    for path in (root / "workflow" / "asset_promotions").glob("*_promotion.json"):
        payload = _read_json(path)
        if payload.get("schema") == "literary-engineering-workbench/candidate-asset-promotion/v0.1":
            asset_type = str(payload.get("asset_type") or "").strip()
            if asset_type:
                result.add(asset_type)
    return result


def _check(
    checks: list[dict[str, Any]],
    check_id: str,
    passed: bool,
    success: str,
    failure: str,
) -> None:
    checks.append(
        {
            "id": check_id,
            "status": "pass" if passed else "error",
            "detail": success if passed else failure,
        }
    )


def _read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}
