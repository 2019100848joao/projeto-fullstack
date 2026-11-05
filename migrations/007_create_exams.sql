CREATE TABLE exams (
    id CHAR(26) PRIMARY KEY,
    appointment_id CHAR(26) NOT NULL REFERENCES appointments (id),
    patient_id CHAR(26) NOT NULL REFERENCES users (id),
    doctor_id CHAR(26) NOT NULL REFERENCES users (id),
    name VARCHAR(255) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'requested',
    scheduled_at TIMESTAMPTZ,
    performed_at TIMESTAMPTZ,
    result TEXT,
    result_available_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT ck_exams_status
    CHECK (status IN ('requested', 'scheduled', 'performed', 'result_available'))
);

CREATE INDEX ix_exams_patient_id
ON exams (patient_id);

CREATE INDEX ix_exams_appointment_id
ON exams (appointment_id);
