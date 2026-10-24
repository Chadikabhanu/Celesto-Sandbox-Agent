-- Idempotent initialization script for Celesto Sandbox runs ledger
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

-- Ensure a fresh database contains sbx-seeddemo1 with state 'deleted' and execution_target 'celesto_sandbox'
INSERT INTO runs (sandbox_name, state, execution_target, task_id, metadata)
VALUES ('sbx-seeddemo1', 'deleted', 'celesto_sandbox', 'task-seed-01', '{"seeded": true}'::jsonb)
ON CONFLICT (sandbox_name) DO UPDATE
SET state = EXCLUDED.state,
    execution_target = EXCLUDED.execution_target,
    task_id = EXCLUDED.task_id,
    metadata = EXCLUDED.metadata,
    updated_at = CURRENT_TIMESTAMP;
