import unittest
from unittest.mock import MagicMock, patch
import tempfile
from pathlib import Path

from fastapi.testclient import TestClient

from events import build_event
from web_app import SessionManager, create_app


class TestWebApp(unittest.TestCase):
    def setUp(self):
        self.session_manager = SessionManager()
        self.client = TestClient(create_app(session_manager=self.session_manager))

    def test_root_page_contains_inputs_and_log_container(self):
        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertIn('id="api-key"', response.text)
        self.assertIn('id="prompt"', response.text)
        self.assertIn('id="run-button"', response.text)
        self.assertIn('id="export-button"', response.text)
        self.assertIn('id="video-button"', response.text)
        self.assertIn('id="log-list"', response.text)
        self.assertIn("window.localStorage.getItem", response.text)
        self.assertIn("window.localStorage.setItem", response.text)

    def test_run_requires_api_key_and_prompt(self):
        response = self.client.post(
            "/api/run",
            json={"api_key": "   ", "prompt": ""},
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["detail"], "Gemini API key is required.")

    def test_run_returns_409_when_session_is_active(self):
        active_thread = MagicMock()
        active_thread.is_alive.return_value = True
        self.session_manager._thread = active_thread

        response = self.client.post(
            "/api/run",
            json={"api_key": "key", "prompt": "Do a task"},
        )

        self.assertEqual(response.status_code, 409)

    @patch("web_app.threading.Thread")
    def test_run_returns_snapshot_when_session_starts(self, mock_thread_cls):
        mock_thread = MagicMock()
        mock_thread.is_alive.return_value = True
        mock_thread_cls.return_value = mock_thread

        response = self.client.post(
            "/api/run",
            json={"api_key": "key", "prompt": "Do a task"},
        )

        self.assertEqual(response.status_code, 202)
        self.assertEqual(response.json()["status"], "running")
        self.assertTrue(response.json()["active"])

    def test_get_session_reports_states(self):
        response = self.client.get("/api/session")
        self.assertEqual(response.json()["status"], "idle")
        self.assertEqual(response.json()["event_count"], 0)
        self.assertIsNone(response.json()["current_action"])
        self.assertFalse(response.json()["has_video"])

        running_thread = MagicMock()
        running_thread.is_alive.return_value = True
        self.session_manager._thread = running_thread
        self.session_manager._status = "running"
        self.session_manager._publish(
            build_event(
                "function_call_started",
                "Running navigate.",
                {"name": "navigate"},
            )
        )
        response = self.client.get("/api/session")
        self.assertEqual(response.json()["status"], "running")
        self.assertTrue(response.json()["active"])
        self.assertEqual(response.json()["current_action"]["name"], "navigate")

        self.session_manager._thread = None
        self.session_manager._publish(
            build_event("session_completed", "All done.", {"url": "https://example.com"})
        )
        response = self.client.get("/api/session")
        self.assertEqual(response.json()["status"], "completed")
        self.assertEqual(response.json()["last_url"], "https://example.com")
        self.assertFalse(response.json()["active"])
        self.assertIsNone(response.json()["current_action"])

        self.session_manager._publish(build_event("session_failed", "Failed."))
        response = self.client.get("/api/session")
        self.assertEqual(response.json()["status"], "error")

    def test_export_log_returns_event_backlog(self):
        self.session_manager._publish(
            build_event("session_started", "Session started.", {"query": "test"})
        )
        self.session_manager._publish(
            build_event(
                "function_call_finished",
                "Completed navigate.",
                {"name": "navigate", "url": "https://example.com"},
            )
        )

        response = self.client.get("/api/log/export")

        self.assertEqual(response.status_code, 200)
        self.assertIn("attachment; filename=", response.headers["content-disposition"])
        payload = response.json()
        self.assertEqual(payload["session"]["event_count"], 2)
        self.assertEqual(payload["events"][0]["type"], "session_started")
        self.assertEqual(payload["events"][1]["data"]["url"], "https://example.com")

    def test_set_video_path_updates_snapshot(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            video_path = Path(temp_dir) / "session.webm"
            video_path.write_bytes(b"video-data")

            self.session_manager._set_video_path(str(video_path))

            snapshot = self.session_manager.snapshot()
            self.assertTrue(snapshot["has_video"])

    def test_latest_video_returns_file_when_available(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            video_path = Path(temp_dir) / "session.webm"
            video_path.write_bytes(b"video-data")
            self.session_manager._last_video_path = str(video_path)

            response = self.client.get("/api/video/latest")

            self.assertEqual(response.status_code, 200)
            self.assertIn(video_path.name, response.headers["content-disposition"])

    def test_latest_video_returns_404_when_missing(self):
        response = self.client.get("/api/video/latest")

        self.assertEqual(response.status_code, 404)

    def test_websocket_streams_video_ready_event(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            video_path = Path(temp_dir) / "session.webm"
            video_path.write_bytes(b"video-data")

            with self.client.websocket_connect("/api/events") as websocket:
                self.session_manager._set_video_path(str(video_path))
                payload = websocket.receive_json()

            self.assertEqual(payload["type"], "video_ready")
            self.assertEqual(payload["data"]["video_path"], str(video_path))

    def test_websocket_replays_backlog_and_streams_new_events(self):
        self.session_manager._publish(build_event("session_started", "Session started."))

        with self.client.websocket_connect("/api/events") as websocket:
            replayed = websocket.receive_json()
            self.assertEqual(replayed["type"], "session_started")

            self.session_manager._publish(
                build_event(
                    "function_call_finished",
                    "Completed navigate.",
                    {"url": "https://example.com"},
                )
            )
            streamed = websocket.receive_json()
            self.assertEqual(streamed["type"], "function_call_finished")
            self.assertEqual(streamed["data"]["url"], "https://example.com")


if __name__ == "__main__":
    unittest.main()
