import unittest
from unittest.mock import MagicMock
from pathlib import Path
import tempfile

from computers.playwright.playwright import PlaywrightComputer


class TestPlaywrightComputerVisualFeedback(unittest.TestCase):
    def test_show_action_banner_evaluates_when_highlight_enabled(self):
        computer = PlaywrightComputer(screen_size=(1440, 900), highlight_mouse=True)
        computer._page = MagicMock()

        computer._show_action_banner("Clicking at 10, 20")

        computer._page.evaluate.assert_called_once()

    def test_show_action_banner_skips_when_highlight_disabled(self):
        computer = PlaywrightComputer(screen_size=(1440, 900), highlight_mouse=False)
        computer._page = MagicMock()

        computer._show_action_banner("Clicking at 10, 20")

        computer._page.evaluate.assert_not_called()

    def test_context_options_enable_video_recording(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            computer = PlaywrightComputer(
                screen_size=(1440, 900),
                record_video=True,
                video_output_dir=temp_dir,
            )

            options = computer._context_options()

            self.assertEqual(options["record_video_dir"], temp_dir)
            self.assertEqual(options["record_video_size"]["width"], 1440)
            self.assertTrue(Path(temp_dir).exists())

    def test_context_options_skip_video_when_disabled(self):
        computer = PlaywrightComputer(screen_size=(1440, 900), record_video=False)

        options = computer._context_options()

        self.assertNotIn("record_video_dir", options)


if __name__ == "__main__":
    unittest.main()
