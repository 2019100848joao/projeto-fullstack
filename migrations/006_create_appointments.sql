CREATE TABLE appointments (
    id CHAR(26) PRIMARY KEY,
    patient_id CHAR(26) NOT NULL REFERENCES users (id),
    doctor_id CHAR(26) NOT NULL REFERENCES users (id),
    created_by CHAR(26) NOT NULL REFERENCES users (id),
    scheduled_at TIMESTAMPTZ NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'scheduled',
    observations TEXT,
    consultation_info TEXT,
    attended_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT ck_appointments_status
    CHECK (status IN ('scheduled', 'cancelled', 'completed'))
);

CREATE INDEX ix_appointments_doctor_scheduled_at
ON appointments (doctor_id, scheduled_at);

CREATE INDEX ix_appointments_patient_id
ON appointments (patient_id);
