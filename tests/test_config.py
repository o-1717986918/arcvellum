import tempfile
from pathlib import Path
import unittest

from literary_engineering_studio.config import default_config, save_config


class ConfigTests(unittest.TestCase):
    def test_default_config_has_no_model_provider(self):
        config = default_config()
        self.assertNotIn("model", config)
        self.assertNotIn("profiles", config)
        self.assertIn("runtimes", config)

    def test_rejects_api_key_fields(self):
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / "config.json"
            with self.assertRaises(ValueError):
                save_config({"api_key": "test-placeholder-key"}, target)


if __name__ == "__main__":
    unittest.main()

