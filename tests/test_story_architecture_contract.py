import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from literary_engineering_studio_engine.agent_tasks import write_agent_completion_marker
from literary_engineering_studio_engine.story_architecture import (
    ARCHITECTURE_REVIEW_SCHEMA,
    ARCHITECTURE_SCHEMA,
    candidate_path,
    prepare_story_architecture,
    prepare_story_architecture_review,
    review_path,
    story_architecture_status,
)


class StoryArchitectureContractTests(unittest.TestCase):
    def test_requires_independent_digest_bound_review_before_longform_can_continue(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "plot").mkdir()
            (root / "project.yaml").write_text("target_length: 500000\n", encoding="utf-8")
            (root / "plot" / "outline.md").write_text("# outline\n", encoding="utf-8")
            candidate, task = prepare_story_architecture(root)
            payload = json.loads(candidate.read_text(encoding="utf-8"))
            payload.update({
                "schema": ARCHITECTURE_SCHEMA,
                "status": "complete",
                "writer_session_id": "writer-1",
                "premise": "A promise costs a city.",
                "central_dramatic_question": "Can the protagonist keep the promise without becoming the tyrant?",
                "protagonist_initial_misbelief": "Control prevents loss.",
                "protagonist_desire": "Save a sibling.",
                "protagonist_need": "Share responsibility.",
                "counterforce": "A rival turns every rescue into public debt.",
                "thematic_contradiction": "Care can become possession.",
                "change_vector": "Control to accountable trust.",
                "midpoint_irreversibility": "The city learns the promise was forged.",
                "endgame_choice": "Break the promise or rule through it.",
                "ending_state": "The city owns the cost together.",
                "volume_obligations": ["Volume one creates the debt."],
                "non_negotiable_payoffs": ["The forged promise is exposed."],
            })
            candidate.write_text(json.dumps(payload), encoding="utf-8")
            write_agent_completion_marker(task, root=root)

            self.assertFalse(story_architecture_status(root)[0])
            review, review_task = prepare_story_architecture_review(root)
            review_payload = json.loads(review.read_text(encoding="utf-8"))
            review_payload.update({
                "schema": ARCHITECTURE_REVIEW_SCHEMA,
                "status": "complete",
                "candidate_sha256": hashlib.sha256(candidate.read_bytes()).hexdigest(),
                "writer_session_id": "writer-1",
                "reviewer_session_id": "reviewer-2",
                "verdict": "pass",
                "findings": [],
                "required_changes": [],
            })
            review.write_text(json.dumps(review_payload), encoding="utf-8")
            write_agent_completion_marker(review_task, root=root)

            passed, message, _ = story_architecture_status(root)
            self.assertTrue(passed, message)

            review_payload["reviewer_session_id"] = "writer-1"
            review_path(root).write_text(json.dumps(review_payload), encoding="utf-8")
            self.assertFalse(story_architecture_status(root)[0])


if __name__ == "__main__":
    unittest.main()
