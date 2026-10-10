# executor package: core execution engine, handler registry, revert service

# Register HubSpot write handlers at import time.
# This module is imported by the Celery worker and by tests.
def _register_handlers() -> None:
    from app.connectors.google.writes import (
        calendar_meeting_handler,
        gmail_draft_handler,
    )
    from app.connectors.hubspot.writes import (
        hubspot_field_update_handler,
        hubspot_note_handler,
        hubspot_task_handler,
    )
    from app.connectors.slack.writes import slack_internal_handler
    from app.executor.core import register_handler

    register_handler("crm_task", hubspot_task_handler)  # type: ignore[arg-type]
    register_handler("crm_note", hubspot_note_handler)  # type: ignore[arg-type]
    register_handler("crm_field_update", hubspot_field_update_handler)  # type: ignore[arg-type]
    register_handler("email_draft", gmail_draft_handler)  # type: ignore[arg-type]
    register_handler("meeting_request", calendar_meeting_handler)  # type: ignore[arg-type]
    register_handler("slack_internal", slack_internal_handler)  # type: ignore[arg-type]


_register_handlers()
