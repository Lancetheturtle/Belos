-- Additive only. Baselines and pre-reset backups stay in Tiger Data.
CREATE TABLE IF NOT EXISTS belos_transport_checkpoints (
    id VARCHAR PRIMARY KEY,
    kind VARCHAR NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL,
    body JSON NOT NULL
);
