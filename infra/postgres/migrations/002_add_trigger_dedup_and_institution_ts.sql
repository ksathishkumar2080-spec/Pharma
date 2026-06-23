-- Layer 12: dedup_key column + institution change timestamp
ALTER TABLE trigger_events ADD COLUMN IF NOT EXISTS dedup_key VARCHAR(32) UNIQUE;
ALTER TABLE hcps ADD COLUMN IF NOT EXISTS institution_updated_at TIMESTAMPTZ DEFAULT NOW();

-- Conference presentations table (if not already present)
CREATE TABLE IF NOT EXISTS conference_presentations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    hcp_id UUID REFERENCES hcps(id) ON DELETE SET NULL,
    conference_name VARCHAR(200) NOT NULL,
    title TEXT NOT NULL,
    presentation_date DATE,
    abstract_url TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Grants table
CREATE TABLE IF NOT EXISTS grants (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    hcp_id UUID REFERENCES hcps(id) ON DELETE SET NULL,
    agency VARCHAR(200),
    title TEXT,
    amount NUMERIC(14,2),
    award_date DATE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_trigger_events_dedup ON trigger_events(dedup_key);
CREATE INDEX IF NOT EXISTS ix_conf_pres_hcp ON conference_presentations(hcp_id);
CREATE INDEX IF NOT EXISTS ix_grants_hcp ON grants(hcp_id);
