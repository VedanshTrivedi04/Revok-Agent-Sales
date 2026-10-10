"""row level security on every tenant table

Revision ID: 0002
Revises: 0001
"""

from alembic import op

from app.db.rls import apply_tenant_rls, drop_tenant_rls

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

# Frozen list: later migrations call apply_tenant_rls() for their own new tables.
TENANT_TABLES = [
    "memberships", "invites", "api_keys", "integrations", "oauth_tokens", "sync_runs",
    "field_mappings", "accounts", "contacts", "deals", "events", "usage_snapshots",
    "entity_match_reviews", "signals", "rules", "rule_hits", "findings", "finding_evidence",
    "agent_runs", "action_cards", "executions", "autonomy_policies", "decision_log",
    "notifications", "outcomes", "edit_feedback",
]  # fmt: skip


def upgrade() -> None:
    for table in TENANT_TABLES:
        apply_tenant_rls(op, table)
    # organizations is tenant-scoped by its own id.
    apply_tenant_rls(op, "organizations", column="id")

    # decision_log is append-only: no UPDATE/DELETE for the runtime role; admin may only
    # DELETE (30-day org purge). A trigger additionally blocks UPDATE for every role.
    op.execute("REVOKE UPDATE, DELETE, TRUNCATE ON decision_log FROM app")
    op.execute("REVOKE UPDATE, TRUNCATE ON decision_log FROM admin")
    op.execute(
        """
        CREATE FUNCTION decision_log_no_update() RETURNS trigger AS $$
        BEGIN
          RAISE EXCEPTION 'decision_log is append-only';
        END $$ LANGUAGE plpgsql
        """
    )
    op.execute(
        "CREATE TRIGGER decision_log_no_update BEFORE UPDATE ON decision_log "
        "FOR EACH ROW EXECUTE FUNCTION decision_log_no_update()"
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS decision_log_no_update ON decision_log")
    op.execute("DROP FUNCTION IF EXISTS decision_log_no_update()")
    op.execute("GRANT UPDATE, DELETE ON decision_log TO app")
    op.execute("GRANT UPDATE ON decision_log TO admin")
    drop_tenant_rls(op, "organizations")
    for table in reversed(TENANT_TABLES):
        drop_tenant_rls(op, table)
