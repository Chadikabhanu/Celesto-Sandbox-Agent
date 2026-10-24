import json
import logging
import asyncio
from typing import Any
import asyncpg
from asyncpg.exceptions import UniqueViolationError
from src.config import settings

logger = logging.getLogger(__name__)

_pool: asyncpg.Pool | None = None


async def get_db_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        raise RuntimeError("Database connection pool is not initialized.")
    return _pool


async def init_db_pool(retries: int = 10, delay: float = 2.0) -> asyncpg.Pool:
    """Initialize database connection pool with retry mechanism."""
    global _pool
    if _pool is not None:
        return _pool

    dsn = settings.DATABASE_URL
    # Normalize SQLAlchemy style asyncpg url if provided
    if dsn.startswith("postgresql+asyncpg://"):
        dsn = dsn.replace("postgresql+asyncpg://", "postgresql://", 1)

    for attempt in range(1, retries + 1):
        try:
            logger.info("Connecting to database ledger (attempt %d/%d)...", attempt, retries)
            _pool = await asyncpg.create_pool(
                dsn=dsn,
                min_size=2,
                max_size=10,
                command_timeout=30.0,
            )
            logger.info("Successfully connected to database ledger.")
            await ensure_schema()
            return _pool
        except Exception as exc:
            logger.warning("Database connection failed on attempt %d: %s", attempt, exc)
            if attempt == retries:
                logger.error("Failed to initialize database connection pool after %d attempts.", retries)
                raise
            await asyncio.sleep(delay)

    raise RuntimeError("Could not connect to database.")


async def close_db_pool() -> None:
    """Gracefully close database pool."""
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None
        logger.info("Database connection pool closed.")


async def ensure_schema() -> None:
    """Ensure runs table and initial seed record exist idempotently."""
    pool = await get_db_pool()
    schema_sql = """
    CREATE TABLE IF NOT EXISTS runs (
        id SERIAL PRIMARY KEY,
        sandbox_name VARCHAR(128) NOT NULL UNIQUE,
        state VARCHAR(64) NOT NULL,
        execution_target VARCHAR(64) NOT NULL,
        task_id VARCHAR(128),
        metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
        created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
    );

    CREATE INDEX IF NOT EXISTS idx_runs_state ON runs (state);
    CREATE INDEX IF NOT EXISTS idx_runs_sandbox_name ON runs (sandbox_name);

    CREATE TABLE IF NOT EXISTS sandbox_events (
        id SERIAL PRIMARY KEY,
        sandbox_name VARCHAR(128) NOT NULL,
        event_type VARCHAR(64) NOT NULL,
        state_before VARCHAR(64) NOT NULL,
        state_after VARCHAR(64) NOT NULL,
        metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
        created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    CREATE INDEX IF NOT EXISTS idx_sandbox_events_name ON sandbox_events (sandbox_name);

    INSERT INTO runs (sandbox_name, state, execution_target, task_id, metadata)
    VALUES ('sbx-seeddemo1', 'deleted', 'celesto_sandbox', 'task-seed-01', '{"seeded": true}'::jsonb)
    ON CONFLICT (sandbox_name) DO UPDATE
    SET state = EXCLUDED.state,
        execution_target = EXCLUDED.execution_target,
        task_id = EXCLUDED.task_id,
        metadata = EXCLUDED.metadata,
        updated_at = CURRENT_TIMESTAMP;
    """
    async with pool.acquire() as conn:
        await conn.execute(schema_sql)
        logger.info("Schema verified, sandbox_events enabled, and idempotent seed ensured.")


async def check_db_health() -> bool:
    """Verify database connectivity."""
    try:
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            result = await conn.fetchval("SELECT 1")
            return result == 1
    except Exception as exc:
        logger.error("Database health check failed: %s", exc)
        return False


async def fetch_all_runs() -> list[dict[str, Any]]:
    """Retrieve all persisted run records ordered by creation."""
    pool = await get_db_pool()
    query = """
    SELECT id, sandbox_name, state, execution_target, task_id, metadata, created_at, updated_at
    FROM runs
    ORDER BY id ASC;
    """
    async with pool.acquire() as conn:
        records = await conn.fetch(query)
        result = []
        for r in records:
            meta = r["metadata"]
            if isinstance(meta, str):
                try:
                    meta = json.loads(meta)
                except Exception:
                    pass
            result.append({
                "id": r["id"],
                "sandbox_name": r["sandbox_name"],
                "state": r["state"],
                "execution_target": r["execution_target"],
                "task_id": r["task_id"],
                "metadata": meta if isinstance(meta, dict) else {},
                "created_at": r["created_at"],
                "updated_at": r["updated_at"],
            })
        return result


async def insert_run(
    sandbox_name: str,
    state: str,
    execution_target: str,
    task_id: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Insert a new run record with parameterized query and transaction."""
    pool = await get_db_pool()
    query = """
    INSERT INTO runs (sandbox_name, state, execution_target, task_id, metadata)
    VALUES ($1, $2, $3, $4, $5::jsonb)
    RETURNING id, sandbox_name, state, execution_target, task_id, metadata, created_at, updated_at;
    """
    metadata_json = json.dumps(metadata or {})
    async with pool.acquire() as conn:
        async with conn.transaction():
            try:
                row = await conn.fetchrow(
                    query,
                    sandbox_name,
                    state,
                    execution_target,
                    task_id,
                    metadata_json,
                )
                if not row:
                    raise RuntimeError("Failed to insert run record.")
                meta = row["metadata"]
                if isinstance(meta, str):
                    try:
                        meta = json.loads(meta)
                    except Exception:
                        pass
                return {
                    "id": row["id"],
                    "sandbox_name": row["sandbox_name"],
                    "state": row["state"],
                    "execution_target": row["execution_target"],
                    "task_id": row["task_id"],
                    "metadata": meta if isinstance(meta, dict) else {},
                    "created_at": row["created_at"],
                    "updated_at": row["updated_at"],
                }
            except UniqueViolationError:
                raise ValueError(f"Run with sandbox_name '{sandbox_name}' already exists.")


async def update_run_state(
    sandbox_name: str,
    new_state: str,
    metadata_patch: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Update run state and record a lifecycle transition event atomically in the ledger."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            row = await conn.fetchrow(
                "SELECT state, metadata FROM runs WHERE sandbox_name = $1",
                sandbox_name,
            )
            if not row:
                raise ValueError(f"Run with sandbox_name '{sandbox_name}' not found.")

            state_before = row["state"]
            current_meta = row["metadata"]
            if isinstance(current_meta, str):
                try:
                    current_meta = json.loads(current_meta)
                except Exception:
                    current_meta = {}
            if metadata_patch:
                current_meta.update(metadata_patch)

            updated_row = await conn.fetchrow(
                """
                UPDATE runs
                SET state = $1, metadata = $2::jsonb, updated_at = CURRENT_TIMESTAMP
                WHERE sandbox_name = $3
                RETURNING id, sandbox_name, state, execution_target, task_id, metadata, created_at, updated_at;
                """,
                new_state,
                json.dumps(current_meta),
                sandbox_name,
            )

            # Record transition in sandbox_events
            await conn.execute(
                """
                INSERT INTO sandbox_events (sandbox_name, event_type, state_before, state_after, metadata)
                VALUES ($1, $2, $3, $4, $5::jsonb);
                """,
                sandbox_name,
                f"transition_to_{new_state}",
                state_before,
                new_state,
                json.dumps(metadata_patch or {}),
            )

            meta = updated_row["metadata"]
            if isinstance(meta, str):
                try:
                    meta = json.loads(meta)
                except Exception:
                    meta = {}

            return {
                "id": updated_row["id"],
                "sandbox_name": updated_row["sandbox_name"],
                "state": updated_row["state"],
                "execution_target": updated_row["execution_target"],
                "task_id": updated_row["task_id"],
                "metadata": meta,
                "created_at": updated_row["created_at"],
                "updated_at": updated_row["updated_at"],
            }


async def fetch_lifecycle_events(sandbox_name: str) -> list[dict[str, Any]]:
    """Retrieve all lifecycle events for a given sandbox."""
    pool = await get_db_pool()
    query = """
    SELECT id, sandbox_name, event_type, state_before, state_after, metadata, created_at
    FROM sandbox_events
    WHERE sandbox_name = $1
    ORDER BY id ASC;
    """
    async with pool.acquire() as conn:
        records = await conn.fetch(query, sandbox_name)
        events = []
        for r in records:
            meta = r["metadata"]
            if isinstance(meta, str):
                try:
                    meta = json.loads(meta)
                except Exception:
                    meta = {}
            events.append({
                "id": r["id"],
                "sandbox_name": r["sandbox_name"],
                "event_type": r["event_type"],
                "state_before": r["state_before"],
                "state_after": r["state_after"],
                "metadata": meta,
                "created_at": r["created_at"],
            })
        return events

