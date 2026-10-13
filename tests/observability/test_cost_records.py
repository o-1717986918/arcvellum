"""Usage accounting survives the UI display window and does not invent billing."""
import unittest
from literary_engineering_studio.observability.live_events import LiveEventBus
from literary_engineering_studio.observability.creative_live.snapshot import build_creative_live_snapshot
from literary_engineering_studio.runtime.usage_accounting import summarize_usage_events


class CostRecordTests(unittest.TestCase):
    def test_display_eviction_does_not_remove_accounting_or_duplicate_usage(self):
        bus=LiveEventBus(max_events_per_channel=50)
        data={"usage_id":"arcvellum-conversation-retained-one","invocation_id":"call",
              "usage":{"total_tokens":100,"input":70,"output":30,"reasoning":20},"cost_usd":0.1}
        bus.publish("project","role.invocation.started",{"invocation_id":"call"})
        bus.publish("project","usage.updated",data)
        for i in range(300):
            bus.publish("project","agent.message.delta",{"text":"雨","index":i})
        self.assertEqual(len(bus.wait_since("project",0,timeout=0)),50)
        events=bus.accounting_events("project")
        events.append({"event":"usage.updated","sequence":400,"data":data})
        snapshot=build_creative_live_snapshot("/work",events)
        self.assertEqual(snapshot["usage"]["total_tokens"],100)
        self.assertEqual(snapshot["usage_accounting"]["outer_invocations"],1)
        self.assertEqual(snapshot["usage_accounting"]["token_details"]["output"],30)
        self.assertIsNone(snapshot["usage_accounting"]["actual_charge"])

    def test_failed_call_without_response_has_unknown_usage_and_independent_actual_charge(self):
        events=[{"event":"role.invocation.started","data":{"invocation_id":"failed"}},
            {"event":"runner.provider.request.started","data":{"model_request_id":"turn"}},
            {"event":"runner.http.attempt.started","data":{"http_attempt_id":"402"}}]
        result=summarize_usage_events(events)
        self.assertEqual(result["unknown_usage_invocations"],1)
        self.assertFalse(result["public_estimate_complete"])
        self.assertIsNone(result["public_estimate_cny"])
        record={"event":"billing.actual_charge.recorded","data":{"record_id":"reported","amount":7.84,
            "currency":"CNY","source":"user-reported","scope_id":"old-acceptance","observed_at":"2026-10-11"}}
        result=summarize_usage_events([*events,record,record])
        self.assertEqual(result["actual_charge"]["amount"],7.84)
        self.assertEqual(len(result["actual_charge_records"]),1)
