import unittest

from literary_engineering_studio.core_bridge import parse_cli_fields


class CoreBridgeTests(unittest.TestCase):
    def test_parses_formal_cli_fields(self):
        fields = parse_cli_fields("status: issued\ntask_id: scene-demo\nmessage: task issued\n")
        self.assertEqual(fields["status"], "issued")
        self.assertEqual(fields["task_id"], "scene-demo")


if __name__ == "__main__":
    unittest.main()
