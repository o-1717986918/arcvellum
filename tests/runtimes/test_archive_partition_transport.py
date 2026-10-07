import unittest
from literary_engineering_studio.runtimes.archive_partition_transport import normalize_archive_partitions


class ArchivePartitionTransportTests(unittest.TestCase):
    def test_exact_aliases_and_other_roles_keep_their_archive_source(self):
        payload={'material_requests':[
            {'kind':'actor','archive_attachments':[{'path':'a.yaml','knowledge':'character_known'},{'path':'b.yaml','knowledge':'creator_reference'}]},
            {'kind':'environment','archive_attachments':[{'path':'b.yaml','knowledge':'creator_reference'}]}]}
        result=normalize_archive_partitions(payload)
        self.assertEqual([item['knowledge'] for request in result['material_requests'] for item in request['archive_attachments']],['known','reference',''])
        self.assertEqual(len(result['attachment_partition_recovery']),3)
        self.assertEqual(result['material_requests'][1]['archive_attachments'][0]['path'],'b.yaml')

    def test_unknown_actor_classification_stays_invalid(self):
        payload={'material_requests':[{'kind':'actor','archive_attachments':[{'path':'a','knowledge':'unknown'}]}]}
        self.assertEqual(normalize_archive_partitions(payload),payload)
