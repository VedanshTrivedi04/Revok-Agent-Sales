"""Importing this package registers every endpoint declared with @endpoint (see app/contract.py)."""

from app.routes import (  # noqa: F401
    accounts,
    action_cards,
    admin,
    api_keys,
    auth,
    autonomy,
    entity_reviews,
    findings,
    health,
    ingest,
    integrations,
    log,
    me,
    members,
    notifications,
    orgs,
    rules,
    runs,
    slack,
    stream,
)
