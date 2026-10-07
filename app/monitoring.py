import os

import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.logging import LoggingIntegration
from sentry_sdk.integrations.starlette import StarletteIntegration

from app.config import settings


def scrub_error_event(event, hint):
    exceptions = event.get("exception", {}).get("values", [])
    if not exceptions:
        return None

    # Learner text can appear in exception messages, request data and frame locals.
    clean = {
        key: event[key]
        for key in ("event_id", "timestamp", "platform", "level", "release", "environment")
        if key in event
    }
    clean["tags"] = {"service": "analyzer", "runtime": "python"}
    if event.get("tags", {}).get("monitoring_smoke") in (True, "true"):
        clean["tags"]["monitoring_smoke"] = "true"
    clean["exception"] = {"values": []}
    for exception in exceptions:
        clean["exception"]["values"].append({
            "type": exception.get("type"),
            "value": "[details removed]",
            "mechanism": {
                key: value for key, value in exception.get("mechanism", {}).items()
                if key in ("type", "handled")
            },
            "stacktrace": {"frames": [
                {key: value for key, value in frame.items()
                 if key in ("filename", "abs_path", "function", "module", "lineno", "in_app")}
                for frame in exception.get("stacktrace", {}).get("frames", [])
            ]},
        })
    return clean


def init_monitoring():
    enabled = settings.SENTRY_ENABLED
    if enabled is None:
        enabled = bool(os.environ.get("RAILWAY_ENVIRONMENT_ID"))
    if not enabled:
        return

    sentry_sdk.init(
        dsn=settings.SENTRY_DSN,
        environment=settings.SENTRY_ENVIRONMENT or os.environ.get("RAILWAY_ENVIRONMENT_NAME", "development"),
        release=settings.SENTRY_RELEASE or os.environ.get("RAILWAY_GIT_COMMIT_SHA"),
        integrations=[
            FastApiIntegration(failed_request_status_codes={500}),
            StarletteIntegration(failed_request_status_codes={500}),
            LoggingIntegration(level=None, event_level=None, capture_sentry_logs=False),
        ],
        send_default_pii=False,
        include_local_variables=False,
        include_source_context=False,
        max_request_body_size="never",
        max_breadcrumbs=0,
        traces_sample_rate=0,
        enable_logs=False,
        enable_metrics=False,
        send_client_reports=False,
        before_send=scrub_error_event,
    )
