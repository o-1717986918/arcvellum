"""Reuse the installed role runtime and archive reader for separate user dialogues."""
from pathlib import Path
import json
from uuid import uuid4
from ..runtime.role_conversation import RoleConversationGateway
from ..runtimes.scene_creator_workspace import SceneCreatorWorkspace
from ..runtimes.scene_natural_output import NaturalOutputProcessor
from literary_engineering_studio_engine.public.prompting import prompt_layer_spec

class CharacterChatRuntimeAdapter:
    def __init__(self, gateway: RoleConversationGateway):
        self.gateway = gateway

    def reply(self, project_root, *, system, history, prompt, timeout):
        return self.gateway.run_actor_turn(project_root, initialization=system,
            initialization_answer="", history=history, prompt=prompt, timeout=timeout).answer

    def draft_card(self, project_root, *, guidance, context):
        def invoke(system, prompt):
            envelope = json.dumps({"schema": "arcvellum/default-conversation/v1",
                "system_prompt": system, "prompt": prompt}, ensure_ascii=False)
            return self.gateway.run(project_root, envelope, role="worker", timeout=300).answer
        prompt = "为这段独立对话填写角色卡。\n" + json.dumps(context, ensure_ascii=False)
        answer = invoke(guidance, prompt)
        processor = NaturalOutputProcessor(self.gateway.data_root / "cards" / str(uuid4()),
            prompt_layer_spec("scene.v2.transport.extractor").default_text, invoke)
        payload = processor.process(answer, kind="card", context=context)
        return {"card": payload["card"], "draft_text": answer}

class CharacterChatArchiveAdapter:
    def __init__(self, data_root: Path):
        self.data_root = data_root

    def list(self, project_root, *, prefix, cursor):
        return SceneCreatorWorkspace(project_root, self.data_root).list_archive(prefix=prefix, cursor=cursor)

    def read(self, project_root, path, *, offset):
        return SceneCreatorWorkspace(project_root, self.data_root).read_archive(path, offset=offset)

    def freeze(self, project_root, attachments):
        return SceneCreatorWorkspace(project_root, self.data_root).freeze_attachments(attachments, kind="actor")

