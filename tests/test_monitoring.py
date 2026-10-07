import json
import os
from pathlib import Path
import runpy
import unittest
from unittest.mock import Mock, patch

import sentry_sdk
from fastapi.testclient import TestClient
from sentry_sdk.transport import Transport

from app.config import settings
from app.monitoring import init_monitoring


class MonitoringTest(unittest.TestCase):
    def test_local_reporting_is_opt_in_and_railway_can_be_disabled(self):
        with patch.dict(os.environ, {}, clear=True), patch("sentry_sdk.init") as initialize:
            with patch.object(settings, "SENTRY_ENABLED", None):
                init_monitoring()
                initialize.assert_not_called()
                os.environ["RAILWAY_ENVIRONMENT_ID"] = "test-environment"
                init_monitoring()
                initialize.assert_called_once()
            initialize.reset_mock()
            with patch.object(settings, "SENTRY_ENABLED", False):
                init_monitoring()
                initialize.assert_not_called()

    def test_fastapi_reports_private_500_call_sites_but_not_expected_failures(self):
        events = []
        secret = "confidential learner phrase"

        class RecordingTransport(Transport):
            def capture_envelope(self, envelope):
                event = envelope.get_event()
                if event:
                    events.append(event)

        initialize_sdk = sentry_sdk.init
        previous_client = sentry_sdk.get_client()
        self.addCleanup(sentry_sdk.get_global_scope().set_client, previous_client)
        with (
            patch.object(settings, "SENTRY_ENABLED", True),
            patch.object(settings, "SENTRY_ENVIRONMENT", "smoke-test"),
            patch.object(settings, "SENTRY_RELEASE", "voc507-test"),
            patch.object(settings, "ANALYZER_API_KEY", "private-key"),
            patch("sentry_sdk.init", side_effect=lambda **options: initialize_sdk(
                **options, transport=RecordingTransport,
            )),
        ):
            # Exercise startup before middleware construction, as in the deployed process.
            app = runpy.run_path(str(Path(__file__).resolve().parent.parent / "app/main.py"))["app"]

        monitoring_client = sentry_sdk.get_client()
        self.addCleanup(monitoring_client.close)
        with sentry_sdk.isolation_scope() as scope:
            scope.set_user({"id": "private-account"})
            scope.set_extra("text", secret)
            scope.set_tag("monitoring_smoke", True)
            scope.set_tag("private_tag", secret)
            headers = {"X-API-Key": "private-key", "Authorization": "Bearer private-jwt"}
            client = TestClient(app)
            translate_body = {"text": secret, "source_lang": "en", "target_lang": "uk"}
            with patch.object(settings, "ANALYZER_API_KEY", "private-key"):
                self.assertEqual(client.get("/api/image/health").status_code, 401)
                self.assertEqual(client.get("/api/image/health", headers=headers).status_code, 503)
                with patch("app.routers.enrichment.enrich_word", side_effect=ValueError(secret)):
                    response = client.post("/api/enrich-word", json={"text": secret}, headers=headers)
                    self.assertEqual(response.status_code, 500)
                translator = Mock(translate_word=Mock(side_effect=ValueError(secret)))
                with patch("app.routers.translation.get_translator", return_value=translator):
                    self.assertEqual(client.post("/api/translate", json=translate_body, headers=headers).status_code, 500)
                translator.translate_word.side_effect = RuntimeError(secret)
                with patch("app.routers.translation.get_translator", return_value=translator):
                    self.assertEqual(client.post("/api/translate", json=translate_body, headers=headers).status_code, 503)
                translator.translate_word.side_effect = TimeoutError(secret)
                with patch("app.routers.translation.get_translator", return_value=translator):
                    self.assertEqual(client.post("/api/translate", json=translate_body, headers=headers).status_code, 504)
                self.assertEqual(client.post("/api/translate", json={}, headers=headers).status_code, 422)
            sentry_sdk.capture_message(secret)

        self.assertEqual(len(events), 2)
        payload = json.dumps(events)
        for private in (secret, "private-key", "private-jwt", "private-account", "private_tag"):
            self.assertNotIn(private, payload)
        for event in events:
            self.assertEqual(event["tags"], {
                "service": "analyzer", "runtime": "python", "monitoring_smoke": "true",
            })
            self.assertEqual(event["environment"], "smoke-test")
            self.assertEqual(event["release"], "voc507-test")
            cause = next(item for item in event["exception"]["values"] if item["type"] == "ValueError")
            self.assertTrue(cause["stacktrace"]["frames"])
            self.assertTrue(all(
                frame.get("filename") and frame.get("lineno")
                for frame in cause["stacktrace"]["frames"]
            ))


if __name__ == "__main__":
    unittest.main()
