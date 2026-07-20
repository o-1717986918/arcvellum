"""Aggregated, non-blocking application bootstrap state."""

from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor
from datetime import datetime, timezone
import threading
from typing import Any, Callable

from .core_bridge import CoreBridge
from .model_connections import model_connection_status
from .opencode_control import provider_catalog
from .project_manager import list_projects


BOOTSTRAP_SCHEMA = "arcvellum/application-bootstrap/v0.1"


class ApplicationBootstrapService:
    """Collect local readiness while warming optional Agent services in the background."""

    def __init__(
        self,
        config: dict[str, Any],
        lifecycle,
        *,
        catalog_loader: Callable[[dict[str, Any]], dict[str, Any]] = provider_catalog,
        project_loader: Callable[[], dict[str, Any]] = list_projects,
        engine_probe: Callable[[], Any] | None = None,
    ):
        self.config = config
        self.lifecycle = lifecycle
        self._catalog_loader = catalog_loader
        self._project_loader = project_loader
        self._engine_probe = engine_probe or (lambda: CoreBridge(config).doctor())
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="arcvellum-bootstrap")
        self._lock = threading.RLock()
        self._catalog_future: Future | None = None
        self._catalog: dict[str, Any] | None = None
        self._catalog_error = ""
        self._catalog_attempted_at = ""
        self._catalog_loaded_at = ""
        self._engine_state: dict[str, Any] | None = None
        self._closed = False

    def start_warmup(self, *, force: bool = False) -> bool:
        """Start one provider-catalog warmup; repeated reads never create a process storm."""
        with self._lock:
            if self._closed:
                return False
            if self._catalog_future is not None and not self._catalog_future.done():
                return False
            if self._catalog is not None and not force:
                return False
            if force:
                self._catalog_error = ""
            self._catalog_attempted_at = _now()
            self._catalog_future = self._executor.submit(self._load_catalog)
            return True

    def snapshot(self) -> dict[str, Any]:
        lifecycle_state, lifecycle_error = self._lifecycle_state()
        engine_state = self._core_engine_state()
        project_state = self._project_state()
        model_state = self._model_state()

        database = lifecycle_state.get("job_store") if isinstance(lifecycle_state.get("job_store"), dict) else {}
        supervisor = (
            lifecycle_state.get("worker_supervisor")
            if isinstance(lifecycle_state.get("worker_supervisor"), dict)
            else {}
        )
        runners = lifecycle_state.get("agent_runners") if isinstance(lifecycle_state.get("agent_runners"), list) else []
        available_runners = [item for item in runners if isinstance(item, dict) and item.get("available")]

        steps = [
            _step(
                "application_database",
                "项目数据库",
                "ready" if database.get("ready") else "blocked",
                blocking=True,
                detail=(
                    f"数据库结构已就绪，记录 {int(database.get('job_count') or 0)} 个执行任务。"
                    if database.get("ready")
                    else lifecycle_error or "项目数据库尚未就绪。"
                ),
                recovery_action="重新启动客户端；若仍失败，请保留数据目录并查看诊断信息。",
            ),
            _step(
                "engine_registry",
                "文学工程内核",
                "ready" if engine_state["ready"] else "blocked",
                blocking=True,
                detail=engine_state["detail"],
                recovery_action="运行应用诊断，确认内核模块和 Python 运行时完整。",
            ),
            _step(
                "job_recovery",
                "任务恢复",
                "ready" if supervisor.get("ready") else "blocked",
                blocking=True,
                detail=(
                    f"任务队列已恢复，当前运行 {len(supervisor.get('active_jobs') or [])} 项。"
                    if supervisor.get("ready")
                    else "后台任务恢复器未就绪。"
                ),
                recovery_action="重新启动客户端，避免在恢复完成前重复提交创作任务。",
            ),
            _step(
                "project_registry",
                "作品目录",
                project_state["status"],
                blocking=False,
                detail=project_state["detail"],
                recovery_action="进入客户端后新建作品，或从本机选择已有作品目录。",
            ),
            _step(
                "agent_runners",
                "创作执行器",
                "ready" if available_runners else "degraded",
                blocking=False,
                detail=(
                    f"已有 {len(available_runners)} 个创作执行器可用。"
                    if available_runners
                    else "暂未发现可用的创作执行器；仍可浏览和整理作品。"
                ),
                recovery_action="在“连接与模型”中安装或连接 OpenCode。",
            ),
            _step(
                "model_catalog",
                "模型与连接",
                model_state["status"],
                blocking=False,
                detail=model_state["detail"],
                recovery_action="在“连接与模型”中重试，或添加模型服务凭证。",
            ),
            _step(
                "update_service",
                "应用更新",
                "deferred",
                blocking=False,
                detail="不影响本次启动；更新检查将在客户端就绪后进行。",
                recovery_action="可稍后在“关于 ArcVellum”中检查更新。",
            ),
        ]
        blocking_ready = all(item["status"] == "ready" for item in steps if item["blocking"])
        degraded = any(item["status"] in {"degraded", "failed"} for item in steps)
        warming = any(item["status"] in {"loading", "waiting"} for item in steps)
        phase = "blocked" if not blocking_ready else "starting" if warming else "degraded" if degraded else "ready"
        completed = sum(1 for item in steps if item["status"] not in {"loading", "waiting"})

        notices = []
        if not available_runners:
            notices.append("创作执行器暂不可用，但你仍可以进入作品、阅读正文和管理资料。")
        if model_state["status"] == "degraded":
            notices.append("模型目录加载失败；这不会阻止客户端启动，可在连接页重试。")

        return {
            "ok": True,
            "schema": BOOTSTRAP_SCHEMA,
            "generated_at": _now(),
            "phase": phase,
            "ready": blocking_ready,
            "can_enter_workspace": blocking_ready,
            "degraded": degraded,
            "progress": {"completed": completed, "total": len(steps)},
            "steps": steps,
            "notices": notices,
            "project": project_state["project"],
            "project_count": project_state["count"],
            "model_catalog": model_state["catalog"],
            "model_warmup": {
                "status": model_state["status"],
                "attempted_at": self._catalog_attempted_at,
                "loaded_at": self._catalog_loaded_at,
                "error": self._catalog_error,
            },
        }

    def shutdown(self) -> None:
        with self._lock:
            if self._closed:
                return
            self._closed = True
        self._executor.shutdown(wait=False, cancel_futures=True)

    def _load_catalog(self) -> None:
        try:
            catalog = self._catalog_loader(self.config)
            if not isinstance(catalog, dict):
                raise RuntimeError("模型目录返回了无法识别的数据。")
        except Exception as exc:
            with self._lock:
                self._catalog_error = str(exc)
            return
        with self._lock:
            self._catalog = catalog
            self._catalog_error = ""
            self._catalog_loaded_at = _now()

    def _lifecycle_state(self) -> tuple[dict[str, Any], str]:
        try:
            return self.lifecycle.health(), ""
        except Exception as exc:
            return {}, str(exc)

    def _core_engine_state(self) -> dict[str, Any]:
        with self._lock:
            cached = self._engine_state
        if cached is not None:
            return cached
        try:
            probe = self._engine_probe()
            returncode = int(getattr(probe, "returncode", 1))
            stderr = str(getattr(probe, "stderr", "") or "").strip()
            state = {
                "ready": returncode == 0,
                "detail": "文学工程内核已就绪。" if returncode == 0 else stderr or "文学工程内核诊断失败。",
            }
        except Exception as exc:
            state = {"ready": False, "detail": str(exc)}
        with self._lock:
            self._engine_state = state
        return state

    def _project_state(self) -> dict[str, Any]:
        try:
            payload = self._project_loader()
            projects = payload.get("projects") if isinstance(payload.get("projects"), list) else []
            current_path = str(payload.get("current_project") or "")
            current = next((item for item in projects if str(item.get("path") or "") == current_path), None)
            if current is None and projects:
                current = projects[0]
            return {
                "status": "ready",
                "detail": (
                    f"已找到 {len(projects)} 部作品，准备打开《{current.get('title') or '未命名作品'}》。"
                    if current
                    else "尚未创建作品，客户端将打开创作起点。"
                ),
                "project": current,
                "count": len(projects),
            }
        except Exception as exc:
            return {
                "status": "degraded",
                "detail": f"作品目录暂时无法读取：{exc}",
                "project": None,
                "count": 0,
            }

    def _model_state(self) -> dict[str, Any]:
        with self._lock:
            future = self._catalog_future
            catalog = dict(self._catalog) if self._catalog is not None else None
            error = self._catalog_error
        if catalog is not None:
            model_count = int(catalog.get("available_model_count") or 0)
            selected = str(catalog.get("selected_model") or "")
            detail = f"已载入 {model_count} 个可用模型"
            if selected:
                detail += f"，当前选择 {selected}"
            return {"status": "ready", "detail": detail + "。", "catalog": catalog}
        if future is not None and not future.done():
            return {"status": "loading", "detail": "正在后台读取模型与连接，不阻塞进入作品。", "catalog": None}
        if error:
            return {"status": "degraded", "detail": f"模型目录暂未载入：{error}", "catalog": None}
        connections = model_connection_status(self.config)
        selected = next((str(item.get("selected_model") or "") for item in connections if item.get("selected_model")), "")
        return {
            "status": "waiting",
            "detail": f"正在准备模型目录{f'（当前选择 {selected}）' if selected else ''}。",
            "catalog": None,
        }


def _step(
    step_id: str,
    label: str,
    status: str,
    *,
    blocking: bool,
    detail: str,
    recovery_action: str,
) -> dict[str, Any]:
    return {
        "id": step_id,
        "label": label,
        "status": status,
        "blocking": blocking,
        "detail": detail,
        "recovery_action": recovery_action,
    }


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
