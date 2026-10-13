import unittest
from literary_engineering_studio.runtime.cache_accounting import summarize_server_cache
from literary_engineering_studio.runtime.usage_accounting import summarize_usage_events


class ServerCacheTests(unittest.TestCase):
    def test_raw_cache_event_on_usage_channel_does_not_add_an_extra_usage_update(self):
        raw={**self.raw("a","reported",0),"channel":"usage","event_id":"raw-a"}
        usage=self.usage("a");usage["data"]["usage"]["total_tokens"]=110
        result=summarize_usage_events([raw,usage,raw,usage])
        self.assertEqual(result["updates"],1)
        self.assertEqual(result["total_tokens"],110)
        self.assertEqual(result["server_cache"]["totals"]["responses"],1)
    def usage(self, identifier, hit=0):
        return {"event":"usage.updated", "data":{"usage_id":identifier,"model_request_id":identifier,
                "provider":"fixture","model":"m","call_purpose":"review",
                "usage":{"input":100-hit,"cache_read":hit,"output":10}}}

    def raw(self, identifier, status, hit=None):
        return {"event":"runner.cache.usage.observed", "data":{"model_request_id":identifier,
                "status":status,"prompt_tokens":100,"cache_read_tokens":hit}}

    def test_missing_zero_positive_and_conflict_are_distinct_and_deduplicated(self):
        usage=self.usage("a")
        events=[usage,usage,self.usage("b"),self.raw("b","reported",0),
                self.usage("c",80),self.raw("c","reported",80),
                self.usage("d"),self.raw("d","inconsistent"),self.usage("e"),self.raw("e","reported",70)]
        totals=summarize_server_cache(events)["totals"]
        self.assertEqual(totals["responses"],5)
        self.assertEqual(totals["unreported_responses"],1)
        self.assertEqual(totals["inconsistent_responses"],2)
        self.assertEqual(totals["hit_ratio"],.4)
        self.assertEqual(totals["reporting_coverage"],.4)

    def test_legacy_positive_is_usable_but_zero_without_raw_field_is_unknown(self):
        totals=summarize_server_cache([self.usage("a",30),self.usage("b")])["totals"]
        self.assertEqual(totals["hit_ratio"],.3)
        self.assertEqual(totals["unreported_responses"],1)
        self.assertIsNone(summarize_server_cache([self.usage("b")])["totals"]["hit_ratio"])
