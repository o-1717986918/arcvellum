"""Character chat API and fresh-project read/SSE verification with an injected role port."""
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from dataclasses import replace
from unittest.mock import patch
from fastapi.testclient import TestClient
from literary_engineering_studio.api_server import create_app
from literary_engineering_studio.config import default_config
from literary_engineering_studio.application.container import build_application_container
from literary_engineering_studio.infrastructure.defaults import build_default_application_ports
from tests.test_character_chat import Conversation
from tests.actor_card_fixtures import actor_card_payload

class CharacterChatApiTests(unittest.TestCase):
    def test_fresh_project_chat_and_read_models(self):
        with TemporaryDirectory() as tmp, patch.dict(os.environ, {"LES_CONFIG_PATH":str(Path(tmp)/"config.json")}):
            directory=Path(tmp)
            config=default_config()
            config["application"].update(data_root=str(directory/"data"),database_path=str(directory/"data/studio.sqlite3"),
                projects_root=str(directory/"projects"))
            ports=replace(build_default_application_ports(config),character_conversation=Conversation())
            container=build_application_container(config,ports)
            with TestClient(create_app(container=container)) as client:
                created=client.post("/projects/create",json={"parent_directory":str(directory),"folder_name":"chat-work",
                    "title":"独立角色对话验收","target_length":5000,"premise":"一封信留在窗边。"})
                self.assertEqual(created.status_code,200,created.text)
                root=created.json()["project"]["path"]
                source=Path(root)/"dialogue-known.md"
                source.write_text("看见了空信封。\n另一段尚未得知的事。",encoding="utf-8")
                for endpoint in ("/health","/projects","/runtime/adapters"):
                    self.assertEqual(client.get(endpoint).status_code,200,endpoint)
                params={"project_root":root}
                self.assertEqual(client.get("/project/workspace",params=params).status_code,200)
                stream=client.get("/project/workspace/stream",params={**params,"max_events":1})
                self.assertEqual(stream.status_code,200)
                self.assertIn("event: workspace.snapshot",stream.text)
                self.assertEqual(len(client.get("/character-chat/setup",params=params).json()["sections"]),16)
                attachment={"path":"dialogue-known.md","start_line":1,"end_line":1,"knowledge":"known"}
                payload={**params,"target":"阿青","card":actor_card_payload(),"context":"雨停了。",
                         "attachments":[attachment]}
                created_chat=client.post("/character-chat/sessions",json=payload)
                self.assertEqual(created_chat.status_code,200,created_chat.text)
                session_id=created_chat.json()["session"]["session_id"]
                answer=client.post(f"/character-chat/sessions/{session_id}/ask",json={**params,"message":"信还在吗？"})
                self.assertEqual(answer.status_code,200,answer.text)
                self.assertIn("信封",answer.json()["session"]["turns"][0]["answer"])
                resumed=client.get(f"/character-chat/sessions/{session_id}",params=params)
                self.assertEqual(len(resumed.json()["session"]["turns"]),1)
                payload["attachments"]=[{"path":"../outside.txt","knowledge":"known"}]
                self.assertEqual(client.post("/character-chat/sessions",json=payload).status_code,400)
            container.shutdown()

