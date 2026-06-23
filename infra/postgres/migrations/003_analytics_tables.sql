-- Layer 18: Analytics & Feedback tables

CREATE TABLE IF NOT EXISTS rep_feedback (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    target_type VARCHAR(50) NOT NULL,  -- message | nba | hcp_score | territory
    target_id TEXT NOT NULL,
    feedback VARCHAR(20) NOT NULL,     -- thumbs_up | thumbs_down | flagged
    rep_id TEXT NOT NULL,
    note TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS message_conversions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    message_id TEXT NOT NULL,
    event VARCHAR(30) NOT NULL,        -- sent | opened | replied | meeting_booked
    rep_id TEXT,
    occurred_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (message_id, event)
);

-- compliance_audit_log (ensure exists from Layer 17 migration)
CREATE TABLE IF NOT EXISTS compliance_audit_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    service VARCHAR(50),
    user_id TEXT,
    method VARCHAR(10),
    path TEXT,
    status_code INT,
    duration_ms INT,
    correlation_id TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_rep_feedback_target ON rep_feedback(target_type, target_id);
CREATE INDEX IF NOT EXISTS ix_msg_conv_message ON message_conversions(message_id);
CREATE INDEX IF NOT EXISTS ix_audit_log_service ON compliance_audit_log(service, created_at);
