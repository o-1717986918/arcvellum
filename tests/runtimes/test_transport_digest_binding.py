from hashlib import sha256
import unittest
from literary_engineering_studio.runtimes.natural_reference_delivery import decode_reference_delivery


class TransportDigestBindingTests(unittest.TestCase):
    def test_missing_transport_metadata_binds_to_the_preserved_original(self):
        text = '这份原始文学交付不改变。'
        result = decode_reference_delivery({'decision':'revise','summary':text}, text)
        self.assertEqual(result['source_sha256'], sha256(text.encode()).hexdigest())
        self.assertEqual(result['summary'], text)

    def test_explicit_foreign_or_reference_digest_still_cannot_bypass_binding(self):
        for digest in ('foreign', {'$source':{'first_block':'b0001'}}):
            with self.subTest(digest=digest), self.assertRaises(ValueError):
                decode_reference_delivery({'source_sha256':digest,'summary':'交付'}, '交付')


if __name__ == '__main__':
    unittest.main()
