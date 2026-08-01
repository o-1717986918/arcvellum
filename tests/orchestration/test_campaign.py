from __future__ import annotations

import unittest

from literary_engineering_studio.orchestration import (
    CampaignPauseReason,
    CampaignPolicy,
    CampaignState,
    campaign_step_allowed,
    campaign_violations,
    checkpoint_due,
)


def _policy(**overrides):
    base = dict(
        scope_kind="chapter",
        scope_key="chapter_01",
        max_autonomous_steps=20,
        checkpoint_interval_steps=5,
        pause_on=(CampaignPauseReason.HUMAN_DECISION,),
    )
    base.update(overrides)
    return CampaignPolicy(**base)


def _state(**overrides):
    base = dict(
        scope_key="chapter_01",
        completed_steps=3,
        last_checkpoint_step=0,
        pending_pause_reasons=(),
    )
    base.update(overrides)
    return CampaignState(**base)


class CampaignTests(unittest.TestCase):
    def test_step_proceeds_within_policy(self):
        decision = campaign_step_allowed(_state(), _policy())

        self.assertTrue(decision.proceed)
        self.assertEqual(decision.reasons, ())

    def test_policy_pause_reason_stops_campaign(self):
        decision = campaign_step_allowed(
            _state(pending_pause_reasons=(CampaignPauseReason.HUMAN_DECISION,)),
            _policy(),
        )

        self.assertFalse(decision.proceed)
        self.assertIn("pause:human-decision", decision.reasons)

    def test_unhandled_pause_reason_fails_closed(self):
        decision = campaign_step_allowed(
            _state(pending_pause_reasons=(CampaignPauseReason.NO_PROGRESS,)),
            _policy(),
        )

        self.assertFalse(decision.proceed)
        self.assertIn("unhandled-pause-reason:no-progress", decision.reasons)

    def test_max_autonomous_steps_stops_campaign(self):
        decision = campaign_step_allowed(
            _state(completed_steps=20),
            _policy(),
        )

        self.assertFalse(decision.proceed)
        self.assertIn("max-autonomous-steps", decision.reasons)

    def test_checkpoint_due_at_interval(self):
        policy = _policy()

        self.assertFalse(checkpoint_due(_state(completed_steps=0), policy))
        self.assertFalse(checkpoint_due(_state(completed_steps=4), policy))
        self.assertTrue(checkpoint_due(_state(completed_steps=5), policy))
        self.assertTrue(checkpoint_due(_state(completed_steps=10), policy))

    def test_campaign_violations(self):
        violations = campaign_violations(
            _state(
                scope_key="chapter_02",
                completed_steps=-1,
                last_checkpoint_step=-1,
            ),
            _policy(
                scope_kind="volume",
                max_autonomous_steps=0,
                checkpoint_interval_steps=0,
            ),
        )

        codes = {item.code for item in violations}
        self.assertEqual(
            codes,
            {
                "scope-mismatch",
                "invalid-scope-kind",
                "invalid-completed-steps",
                "invalid-checkpoint-step",
                "invalid-max-steps",
                "invalid-checkpoint-interval",
            },
        )

    def test_valid_campaign_has_no_violations(self):
        self.assertEqual(campaign_violations(_state(), _policy()), ())


if __name__ == "__main__":
    unittest.main()
