"""Character dialogue HTTP adapter over the application service."""
from typing import Any
from fastapi import APIRouter
from pydantic import BaseModel, Field
from ..common import call_handler, project_root as resolve_root

class CharacterChatCreateRequest(BaseModel):
    project_root: str
    target: str
    card: dict[str, Any]
    attachments: list[dict[str, Any]] = Field(default_factory=list)
    context: str = ""

class CharacterChatMessageRequest(BaseModel):
    project_root: str
    message: str
    timeout: int = 300

class CharacterChatCardRequest(BaseModel):
    project_root: str
    target: str
    attachments: list[dict[str, Any]] = Field(default_factory=list)
    context: str = ""

def build_character_chat_router(service) -> APIRouter:
    router = APIRouter(prefix="/character-chat")

    @router.get("/setup")
    def setup(project_root: str):
        return call_handler(lambda: {"ok": True, **service.setup(resolve_root(project_root))})

    @router.get("/archive")
    def archive(project_root: str, prefix: str = "", cursor: int = 0):
        return call_handler(lambda: {"ok": True, **service.archive_list(
            resolve_root(project_root), prefix=prefix, cursor=cursor)})

    @router.get("/archive/read")
    def archive_read(project_root: str, path: str, offset: int = 0):
        return call_handler(lambda: {"ok": True, **service.archive_read(
            resolve_root(project_root), path, offset=offset)})

    @router.post("/sessions")
    def create(payload: CharacterChatCreateRequest):
        return call_handler(lambda: {"ok": True, "session": service.create(
            resolve_root(payload.project_root), target=payload.target, card=payload.card,
            attachments=payload.attachments, context=payload.context)})

    @router.post("/cards/draft")
    def draft_card(payload: CharacterChatCardRequest):
        return call_handler(lambda: {"ok": True, **service.draft_card(
            resolve_root(payload.project_root), target=payload.target,
            attachments=payload.attachments, context=payload.context)})

    @router.get("/sessions/{session_id}")
    def read(session_id: str, project_root: str):
        return call_handler(lambda: {"ok": True, "session": service.read(resolve_root(project_root), session_id)})

    @router.post("/sessions/{session_id}/ask")
    def ask(session_id: str, payload: CharacterChatMessageRequest):
        return call_handler(lambda: {"ok": True, "session": service.ask(
            resolve_root(payload.project_root), session_id, payload.message, timeout=payload.timeout)})

    return router

