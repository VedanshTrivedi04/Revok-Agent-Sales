"""RLS helpers for Alembic migrations. Every new tenant table must call apply_tenant_rls()."""

from typing import Any

POLICY = "tenant_isolation"
# NULLIF guards the '' that current_setting returns after a transaction-local set_config ends.
_ORG = "NULLIF(current_setting('app.org_id', true), '')::uuid"


def apply_tenant_rls(op: Any, table: str, column: str = "org_id") -> None:
    op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY {POLICY} ON {table} "
        f"USING ({column} = {_ORG}) WITH CHECK ({column} = {_ORG})"
    )


def drop_tenant_rls(op: Any, table: str) -> None:
    op.execute(f"DROP POLICY IF EXISTS {POLICY} ON {table}")
    op.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")
