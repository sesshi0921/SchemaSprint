from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from psycopg import AsyncConnection, sql
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

from .config import Settings
from .security import Principal, token_digest


class Database:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._pool = AsyncConnectionPool[AsyncConnection[dict[str, Any]]](
            conninfo=self.settings.database_dsn.get_secret_value(),
            min_size=self.settings.database_pool_min,
            max_size=self.settings.database_pool_max,
            open=False,
            kwargs={"row_factory": dict_row},
            timeout=10,
        )

    async def open(self) -> None:
        await self._pool.open(wait=True, timeout=15)

    async def close(self) -> None:
        await self._pool.close()

    @asynccontextmanager
    async def privileged(self) -> AsyncIterator[AsyncConnection[dict[str, Any]]]:
        async with (
            self._pool.connection() as connection,
            connection.transaction(),
        ):
            yield connection

    @asynccontextmanager
    async def as_user(
        self, principal: Principal
    ) -> AsyncIterator[AsyncConnection[dict[str, Any]]]:
        async with (
            self._pool.connection() as connection,
            connection.transaction(),
        ):
            await connection.execute("SET LOCAL ROLE authenticated")
            await connection.execute(
                "SELECT set_config('request.jwt.claim.sub', %s, true)",
                (principal.auth_user_id,),
            )
            yield connection

    async def principal_for_token(self, raw_token: str) -> Principal | None:
        digest = token_digest(
            raw_token, self.settings.session_pepper.get_secret_value()
        )
        query = sql.SQL(
            """
            SELECT s.id, s.user_id, u.auth_user_id,
                   coalesce(array_agg(r.role::text) FILTER
                       (WHERE r.role IS NOT NULL), ARRAY[]::text[]) AS roles,
                   EXISTS (SELECT 1 FROM public.provider_identities pi
                           WHERE pi.user_id = u.id AND pi.verified_at IS NOT NULL)
                       AS identity_verified,
                   EXISTS (SELECT 1 FROM public.age_declarations age
                           WHERE age.user_id = u.id AND age.is_at_least_16)
                       AS age_declared,
                   EXISTS (
                       SELECT 1 FROM public.provider_identities pi
                       JOIN private.identity_allowlist al
                         ON al.issuer = pi.issuer AND al.subject = pi.subject
                        AND al.disabled_at IS NULL
                       WHERE pi.user_id = u.id AND pi.verified_at IS NOT NULL
                   ) AS allowlisted,
                   NOT EXISTS (
                       SELECT 1 FROM (
                           SELECT DISTINCT ON (pv.kind) pv.id
                           FROM public.policy_versions pv
                           WHERE pv.required_from <= now()
                           ORDER BY pv.kind, pv.version DESC, pv.required_from DESC
                       ) latest
                       WHERE NOT EXISTS (
                           SELECT 1 FROM public.policy_acknowledgements pa
                           WHERE pa.user_id = u.id AND pa.policy_version_id = latest.id
                       )
                   ) AS policies_current,
                   s.mfa_authenticated_at > now() - interval '15 minutes'
                       AS mfa_current
            FROM private.sessions AS s
            JOIN public.users AS u ON u.id = s.user_id
            LEFT JOIN public.role_grants AS r ON r.user_id = u.id
            WHERE s.token_hash = %s AND s.revoked_at IS NULL AND s.expires_at > now()
            GROUP BY s.id, s.user_id, u.id, u.auth_user_id,
                     s.mfa_authenticated_at
            """
        )
        async with self.privileged() as connection:
            row = await (await connection.execute(query, (digest,))).fetchone()
        if row is None:
            return None
        return Principal(
            session_id=str(row["id"]),
            user_id=str(row["user_id"]),
            auth_user_id=str(row["auth_user_id"]),
            roles=frozenset(str(role) for role in row["roles"]),
            allowlisted=bool(row["allowlisted"]),
            identity_verified=bool(row["identity_verified"]),
            age_declared=bool(row["age_declared"]),
            policies_current=bool(row["policies_current"]),
            mfa_current=bool(row["mfa_current"]),
        )

    async def can_learn(self, principal: Principal) -> bool:
        """Return the database-authoritative learning gate before content access."""
        async with self.as_user(principal) as connection:
            row = await (
                await connection.execute("SELECT public.can_learn() AS allowed")
            ).fetchone()
        return bool(row and row["allowed"])
