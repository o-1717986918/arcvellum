from pathlib import Path
import tempfile
import unittest

from literary_engineering_studio.jobs import JobStore


class ArchivePersistenceTests(unittest.TestCase):
    def test_transaction_and_revisions_share_one_durable_index_write(self):
        with tempfile.TemporaryDirectory() as temporary:
            store = JobStore(Path(temporary) / "studio.sqlite3")
            record = {
                "transaction_id": "owner-transaction-one",
                "project_root": "C:/work",
                "asset_id": "character:lin",
                "asset_type": "character",
                "base_revision": "sha256:" + ("a" * 64),
                "new_revision": "sha256:" + ("b" * 64),
                "authority": "owner",
                "semantic_review": "waived",
                "reason": "作者调整角色权重。",
                "impact": {"stale_categories": ["context"]},
                "stale_propagation": {"status": "propagated", "scene_ids": ["scene_0001"]},
                "receipt_path": "workflow/archive/transactions/owner-transaction-one/receipt.json",
                "transaction_path": "workflow/archive/transactions/owner-transaction-one/transaction.json",
                "before_snapshot": "workflow/archive/transactions/owner-transaction-one/before.yaml",
                "after_snapshot": "workflow/archive/transactions/owner-transaction-one/after.yaml",
                "created_at": "2026-07-25T00:00:00+00:00",
            }

            store.record_asset_transaction(record)

            history = store.list_asset_transactions("C:/work", "character:lin")
            self.assertEqual([item["transaction_id"] for item in history], ["owner-transaction-one"])
            self.assertEqual(history[0]["impact"]["stale_categories"], ["context"])
            self.assertEqual(history[0]["stale_propagation"]["status"], "propagated")
            self.assertEqual(
                store.read_asset_revision("C:/work", "character:lin", "sha256:" + ("a" * 64))["snapshot_path"],
                record["before_snapshot"],
            )
            self.assertEqual(
                store.read_asset_revision("C:/work", "character:lin", "sha256:" + ("b" * 64))["snapshot_path"],
                record["after_snapshot"],
            )

            # Receipt synchronization is idempotent.
            store.record_asset_transaction(record)
            self.assertEqual(len(store.list_asset_transactions("C:/work", "character:lin")), 1)

    def test_schema_migration_adds_archive_indexes_without_losing_existing_jobs(self):
        with tempfile.TemporaryDirectory() as temporary:
            database = Path(temporary) / "studio.sqlite3"
            first = JobStore(database)
            job = first.create({"project_root": "C:/work"})

            restarted = JobStore(database)

            self.assertEqual(restarted.read(job["job_id"])["job_id"], job["job_id"])
            with restarted._connection() as connection:
                tables = {
                    str(row["name"])
                    for row in connection.execute(
                        "SELECT name FROM sqlite_master WHERE type = 'table'"
                    ).fetchall()
                }
            self.assertIn("archive_asset_transactions", tables)
            self.assertIn("archive_asset_revisions", tables)


if __name__ == "__main__":
    unittest.main()
