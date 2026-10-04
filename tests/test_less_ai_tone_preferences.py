import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from literary_engineering_studio.application.config import default_config, load_config
from literary_engineering_studio.application.less_ai_tone_preferences import (
    get_less_ai_tone_preferences, set_less_ai_tone_preferences,
)


class TonePreferenceTests(unittest.TestCase):
    def test_default_and_roundtrip(self):
        config = default_config()
        self.assertFalse(get_less_ai_tone_preferences(config)["enabled"])
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "experiment.json"
            set_less_ai_tone_preferences(config, True, path=path)
            self.assertTrue(get_less_ai_tone_preferences(load_config(path))["enabled"])
            set_less_ai_tone_preferences(config, False, path=path)
            self.assertFalse(json.loads(path.read_text(encoding="utf-8"))["application"]["less_ai_tone_experiment"]["enabled"])

    def test_invalid_input_and_failed_save_leave_live_settings_unchanged(self):
        config = default_config()
        for value in ("true", 1, None):
            with self.assertRaises(ValueError):
                set_less_ai_tone_preferences(config, value)
        with patch("literary_engineering_studio.application.less_ai_tone_preferences.save_config", side_effect=OSError("disk full")):
            with self.assertRaises(OSError):
                set_less_ai_tone_preferences(config, True)
        self.assertFalse(get_less_ai_tone_preferences(config)["enabled"])
