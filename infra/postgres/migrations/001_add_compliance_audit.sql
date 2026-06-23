-- Compliance and Evidence tracking
CREATE TABLE IF NOT EXISTS compliance_audit_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_type TEXT NOT NULL,   -- hcp | message | trigger | publication
    entity_id UUID NOT NULL,
    action TEXT NOT NULL,        -- created | updated | accessed | exported
    performed_by TEXT,
    ip_address TEXT,
    metadata JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Evidence citations for messages
CREATE TABLE IF NOT EXISTS message_evidence (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    message_id UUID REFERENCES outreach_messages(id) ON DELETE CASCADE,
    evidence_type TEXT NOT NULL, -- publication | trial | guideline | news
    source_id UUID,
    source_url TEXT,
    cited_text TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Grant tracking
CREATE TABLE IF NOT EXISTS grants (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    hcp_id UUID REFERENCES hcps(id),
    title TEXT NOT NULL,
    agency TEXT,
    amount NUMERIC,
    start_date DATE,
    end_date DATE,
    disease_areas TEXT[],
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Advisory board memberships
CREATE TABLE IF NOT EXISTS advisory_boards (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    hcp_id UUID REFERENCES hcps(id),
    company TEXT NOT NULL,
    drug_or_program TEXT,
    role TEXT,
    start_date DATE,
    end_date DATE,
    is_competitor BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Conference presentations
CREATE TABLE IF NOT EXISTS conference_presentations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    hcp_id UUID REFERENCES hcps(id),
    conference TEXT NOT NULL,    -- ASCO | ESMO | AACR | SABCS | NCCN | other
    year INT,
    title TEXT,
    abstract_id TEXT,
    presentation_type TEXT,     -- oral | poster | keynote | panel
    disease_area TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_compliance_entity ON compliance_audit_log(entity_type, entity_id);
CREATE INDEX IF NOT EXISTS idx_grants_hcp ON grants(hcp_id);
CREATE INDEX IF NOT EXISTS idx_advisory_hcp ON advisory_boards(hcp_id);
CREATE INDEX IF NOT EXISTS idx_presentations_hcp ON conference_presentations(hcp_id);
