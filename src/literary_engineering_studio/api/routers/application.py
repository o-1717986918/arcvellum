"""Application bootstrap, desktop session, diagnostics, and static UI routes."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse


@dataclass(frozen=True)
class ApplicationRouterDependencies:
    """Explicit dependencies for routes that exist before a project is open."""

    config: dict[str, Any]
    lifecycle: Any
    bootstrap: Any
    version: str
    startup_nonce: str
    api_token: str
    desktop_session_token: str
    model_connection_status: Callable[[dict[str, Any]], list[dict[str, Any]]]
    build_application_info: Callable[[dict[str, Any]], dict[str, Any]]
    build_legal_documents: Callable[[], dict[str, Any]]
    build_diagnostic_report: Callable[[dict[str, Any], Any, Any], dict[str, Any]]
    export_diagnostic_report: Callable[[dict[str, Any], Any, Any], Any]
    stream_read_model: Callable[[str, Callable[[], dict[str, Any]], float, int], Any]
    frontend_file: Callable[[str, str], Any]


def build_application_router(deps: ApplicationRouterDependencies) -> APIRouter:
    """Build stable root/application routes without closing over ``create_app`` globals."""

    router = APIRouter()

    @router.get("/", response_class=HTMLResponse)
    def ui_root():
        return deps.frontend_file("index.html", "text/html; charset=utf-8")

    @router.post("/desktop/session")
    def desktop_session(request: Request):
        if not deps.api_token:
            return {"ok": True, "desktop_auth": "not-required"}
        supplied = request.headers.get("Authorization", "")
        if supplied != f"Bearer {deps.api_token}":
            raise HTTPException(status_code=401, detail="invalid Studio desktop bootstrap token")
        response = JSONResponse({"ok": True, "desktop_auth": "ready"})
        response.set_cookie(
            "les_desktop_session",
            deps.desktop_session_token,
            httponly=True,
            samesite="strict",
            secure=False,
            path="/",
        )
        return response

    @router.get("/ui/{path:path}")
    def ui_asset(path: str):
        suffix = path.rsplit(".", 1)[-1].lower() if "." in path else ""
        content_type = {
            "css": "text/css; charset=utf-8",
            "js": "application/javascript; charset=utf-8",
            "png": "image/png",
            "jpg": "image/jpeg",
            "jpeg": "image/jpeg",
            "svg": "image/svg+xml; charset=utf-8",
            "webp": "image/webp",
            "map": "application/json; charset=utf-8",
        }.get(suffix, "text/plain; charset=utf-8")
        return deps.frontend_file(path, content_type)

    @router.get("/health")
    def health():
        snapshot = deps.bootstrap.snapshot()
        engine_step = next(
            (item for item in snapshot.get("steps", []) if item.get("id") == "engine_registry"),
            {},
        )
        application_state = deps.lifecycle.health()
        return {
            "ok": True,
            "application_id": "arcvellum-studio",
            "protocol_version": "arcvellum-sidecar/v1",
            "version": deps.version,
            "startup_nonce": deps.startup_nonce,
            "engine_ready": engine_step.get("status") == "ready",
            "engine_detail": str(engine_step.get("detail") or ""),
            "agent_runners": application_state.get("agent_runners", []),
            "model_connections": deps.model_connection_status(deps.config),
            "model_connection_policy": "runner-managed",
            "application": application_state,
        }

    @router.get("/application/health")
    def application_health():
        return {"ok": True, **deps.lifecycle.health()}

    @router.get("/application/info")
    def application_info():
        return deps.build_application_info(deps.config)

    @router.get("/application/details")
    def application_details():
        return deps.build_application_info(deps.config)

    @router.get("/application/legal")
    def application_legal():
        return deps.build_legal_documents()

    @router.get("/help")
    def help_center():
        return {
            "ok": True,
            "schema": "arcvellum/help-center/v1",
            "topics": [
                {"id": "first-use", "title": "第一次使用", "summary": "建立作品、写下方向、连接 Agent，然后从创作总控准备下一项任务。"},
                {"id": "gates", "title": "审批与门禁", "summary": "分支、设定写回、修订和交付会在关键节点等待明确决定。"},
                {"id": "models", "title": "Agent 与模型", "summary": "Agent 执行受控任务，模型提供创作判断，正式产物由状态机验收。"},
                {"id": "reader", "title": "阅读与交付", "summary": "阅读器只拼接晋升正文，交付只使用通过正式门禁的内容。"},
                {"id": "troubleshooting", "title": "启动与连接", "summary": "可重新检查本地服务或生成不含正文和凭证的诊断报告。"},
            ],
        }

    @router.get("/application/diagnostics")
    def application_diagnostics():
        return {"ok": True, **deps.build_diagnostic_report(deps.config, deps.lifecycle, deps.bootstrap)}

    @router.post("/application/diagnostics/export")
    def application_diagnostics_export():
        target = deps.export_diagnostic_report(deps.config, deps.lifecycle, deps.bootstrap)
        return FileResponse(target, media_type="application/json", filename=target.name)

    @router.get("/application/bootstrap")
    def application_bootstrap():
        return deps.bootstrap.snapshot()

    @router.get("/application/bootstrap/stream")
    def application_bootstrap_stream(interval_seconds: float = 1.0, max_events: int = 0):
        return deps.stream_read_model("application.bootstrap", deps.bootstrap.snapshot, interval_seconds, max_events)

    @router.post("/application/warmup")
    def application_warmup():
        started = deps.bootstrap.start_warmup(force=True)
        return {"ok": True, "started": started, "bootstrap": deps.bootstrap.snapshot()}

    return router
