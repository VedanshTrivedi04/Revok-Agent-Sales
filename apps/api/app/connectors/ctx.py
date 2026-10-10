"""ConnCtx: what every connector method receives.

Holds org/integration identity, a rate-limited HttpClient and `access_token()`, which decrypts the
stored token and refreshes it (under a Redis lock, persisted atomically in one transaction) when
it expires within REFRESH_MARGIN. A failed refresh marks the integration `needs_reauth`.
"""

from dataclasses import dataclass, field
from datetime import timedelta
from uuid import UUID

from sqlalchemy import select

from app.connectors import registry
from app.connectors.base import OAuthConnector, TokenSet
from app.connectors.http import HttpClient, TokenBucket
from app.db.session import org_session
from app.models.integrations import Integration, OAuthToken
from app.utils.crypto import decrypt, encrypt
from app.utils.errors import AppError
from app.utils.locks import lock
from app.utils.time import utcnow

REFRESH_MARGIN = timedelta(seconds=60)


@dataclass
class ConnCtx:
    org_id: UUID
    integration_id: UUID
    provider: str
    user_id: UUID | None = None
    http: HttpClient = field(default=None)  # type: ignore[assignment]

    @classmethod
    async def load(
        cls, org_id: UUID, integration_id: UUID, *, http: HttpClient | None = None
    ) -> "ConnCtx":
        async with org_session(org_id) as s:
            integ = (
                await s.execute(select(Integration).where(Integration.id == integration_id))
            ).scalar_one_or_none()
        if integ is None:
            raise AppError("not_found", "Integration not found")
        client = http or HttpClient(integ.provider, bucket=TokenBucket(org_id, integ.provider))
        return cls(org_id, integration_id, integ.provider, integ.user_id, client)

    @staticmethod
    def _aad(integration_id: UUID) -> bytes:
        return str(integration_id).encode()

    async def store_tokens(self, tokens: TokenSet) -> None:
        """Encrypt and upsert tokens for this integration (used by OAuth callback and refresh)."""
        aad = self._aad(self.integration_id)
        access = encrypt(tokens.access_token, aad=aad)
        refresh = encrypt(tokens.refresh_token, aad=aad) if tokens.refresh_token else None
        async with org_session(self.org_id) as s:
            row = (
                await s.execute(
                    select(OAuthToken)
                    .where(OAuthToken.integration_id == self.integration_id)
                    .with_for_update()
                )
            ).scalar_one_or_none()
            if row is None:
                row = OAuthToken(
                    org_id=self.org_id,
                    integration_id=self.integration_id,
                    access_token_enc=b"",
                    key_id="",
                )
                s.add(row)
            row.access_token_enc = access.blob
            row.refresh_token_enc = refresh.blob if refresh else row.refresh_token_enc
            row.key_id = access.key_id
            row.expires_at = tokens.expires_at
            row.token_type = tokens.token_type

    async def _read(self) -> tuple[str, str | None, bool]:
        """(access_token, refresh_token, expiring_soon) from the DB."""
        async with org_session(self.org_id) as s:
            row = (
                await s.execute(
                    select(OAuthToken).where(OAuthToken.integration_id == self.integration_id)
                )
            ).scalar_one_or_none()
        if row is None:
            raise AppError(
                "integration_needs_reauth", "No credentials stored; reconnect the integration"
            )
        aad = self._aad(self.integration_id)
        access = decrypt(row.access_token_enc, row.key_id, aad=aad)
        refresh = (
            decrypt(row.refresh_token_enc, row.key_id, aad=aad) if row.refresh_token_enc else None
        )
        expiring = row.expires_at is not None and row.expires_at - utcnow() <= REFRESH_MARGIN
        return access, refresh, expiring

    async def access_token(self) -> str:
        access, refresh, expiring = await self._read()
        if not expiring:
            return access
        async with lock(f"tokenrefresh:{self.integration_id}", ttl=30, wait=10.0):
            access, refresh, expiring = await self._read()  # another worker may have refreshed
            if not expiring:
                return access
            connector = registry.get(self.provider)
            if not refresh or not isinstance(connector, OAuthConnector):
                await self._mark_needs_reauth("Credentials expired and cannot be refreshed")
                raise AppError("integration_needs_reauth", details={"provider": self.provider})
            try:
                tokens = await connector.refresh(refresh)
            except AppError:
                await self._mark_needs_reauth("Provider rejected the refresh token")
                raise
            await self.store_tokens(tokens)
            return tokens.access_token

    async def _mark_needs_reauth(self, message: str) -> None:
        async with org_session(self.org_id) as s:
            integ = (
                await s.execute(
                    select(Integration)
                    .where(Integration.id == self.integration_id)
                    .with_for_update()
                )
            ).scalar_one()
            integ.status = "needs_reauth"
            integ.last_error = message
            integ.error_count += 1

    async def request(self, method: str, url: str, **kwargs: object) -> object:
        """HTTP call with a fresh bearer token (refreshing first if needed)."""
        return await self.http.request(method, url, bearer=await self.access_token(), **kwargs)
