CREATE TABLE role_transition_requests (
    id CHAR(26) PRIMARY KEY,
    user_id CHAR(26) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    requested_role VARCHAR(20) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    reviewed_by_id CHAR(26) NULL REFERENCES users(id) ON DELETE SET NULL,
    reviewed_at TIMESTAMPTZ NULL,
    CONSTRAINT ck_role_transition_requested_role
        CHECK (requested_role IN ('doctor', 'attendant')),
    CONSTRAINT ck_role_transition_status
        CHECK (status IN ('pending', 'approved', 'rejected'))
);

CREATE INDEX ix_role_transition_requests_user_id
    ON role_transition_requests (user_id);

CREATE INDEX ix_role_transition_requests_status
    ON role_transition_requests (status);
