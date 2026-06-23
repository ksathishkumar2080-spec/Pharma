-- Enable extensions
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS unaccent;

-- HCP (Healthcare Professional) master table
CREATE TABLE IF NOT EXISTS hcps (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    full_name TEXT NOT NULL,
    npi TEXT UNIQUE,
    specialty TEXT,
    subspecialty TEXT,
    institution_id UUID,
    city TEXT,
    state TEXT,
    country TEXT DEFAULT 'US',
    email TEXT,
    linkedin_url TEXT,
    twitter_handle TEXT,
    researchgate_url TEXT,
    commercial_score FLOAT DEFAULT 0,
    opportunity_score FLOAT DEFAULT 0,
    influence_score FLOAT DEFAULT 0,
    kol_tier TEXT CHECK (kol_tier IN ('national', 'regional', 'local', 'emerging')),
    is_active BOOLEAN DEFAULT TRUE,
    last_enriched_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Institutions
CREATE TABLE IF NOT EXISTS institutions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    type TEXT CHECK (type IN ('academic', 'community', 'nci_designated', 'private', 'va', 'other')),
    city TEXT,
    state TEXT,
    country TEXT DEFAULT 'US',
    npi TEXT,
    referral_volume_score FLOAT DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Publications
CREATE TABLE IF NOT EXISTS publications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    pubmed_id TEXT UNIQUE,
    title TEXT NOT NULL,
    abstract TEXT,
    journal TEXT,
    published_at DATE,
    doi TEXT,
    citation_count INT DEFAULT 0,
    disease_areas TEXT[],
    biomarkers TEXT[],
    therapies TEXT[],
    embedding vector(1536),
    raw_json JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Publication authorship
CREATE TABLE IF NOT EXISTS publication_authors (
    publication_id UUID REFERENCES publications(id) ON DELETE CASCADE,
    hcp_id UUID REFERENCES hcps(id) ON DELETE CASCADE,
    author_position INT,
    is_corresponding BOOLEAN DEFAULT FALSE,
    PRIMARY KEY (publication_id, hcp_id)
);

-- Clinical Trials
CREATE TABLE IF NOT EXISTS clinical_trials (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    nct_id TEXT UNIQUE NOT NULL,
    title TEXT NOT NULL,
    phase TEXT,
    status TEXT,
    sponsor TEXT,
    conditions TEXT[],
    interventions TEXT[],
    primary_completion_date DATE,
    start_date DATE,
    enrollment INT,
    raw_json JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Trial investigators
CREATE TABLE IF NOT EXISTS trial_investigators (
    trial_id UUID REFERENCES clinical_trials(id) ON DELETE CASCADE,
    hcp_id UUID REFERENCES hcps(id) ON DELETE CASCADE,
    role TEXT CHECK (role IN ('principal', 'sub', 'collaborator')),
    PRIMARY KEY (trial_id, hcp_id)
);

-- Competitors
CREATE TABLE IF NOT EXISTS competitors (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    ticker TEXT,
    disease_areas TEXT[],
    pipeline_assets JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Trigger events
CREATE TABLE IF NOT EXISTS trigger_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    hcp_id UUID REFERENCES hcps(id),
    event_type TEXT NOT NULL,
    event_data JSONB,
    source TEXT,
    occurred_at TIMESTAMPTZ,
    processed BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Outreach messages
CREATE TABLE IF NOT EXISTS outreach_messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    hcp_id UUID REFERENCES hcps(id),
    channel TEXT CHECK (channel IN ('linkedin', 'email', 'conversation_starter', 'follow_up')),
    subject TEXT,
    body TEXT NOT NULL,
    evidence_citations JSONB,
    grammar_validated BOOLEAN DEFAULT FALSE,
    sent_at TIMESTAMPTZ,
    opened_at TIMESTAMPTZ,
    replied_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Relationship memory
CREATE TABLE IF NOT EXISTS relationship_memory (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    hcp_id UUID REFERENCES hcps(id),
    rep_id TEXT,
    interaction_type TEXT,
    notes TEXT,
    sentiment TEXT CHECK (sentiment IN ('positive', 'neutral', 'negative')),
    occurred_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_hcps_specialty ON hcps(specialty);
CREATE INDEX IF NOT EXISTS idx_hcps_state ON hcps(state);
CREATE INDEX IF NOT EXISTS idx_hcps_commercial_score ON hcps(commercial_score DESC);
CREATE INDEX IF NOT EXISTS idx_publications_pubmed ON publications(pubmed_id);
CREATE INDEX IF NOT EXISTS idx_trigger_events_hcp ON trigger_events(hcp_id);
CREATE INDEX IF NOT EXISTS idx_trigger_events_processed ON trigger_events(processed);
CREATE INDEX IF NOT EXISTS idx_publications_embedding ON publications USING ivfflat (embedding vector_cosine_ops);
