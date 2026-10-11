CREATE TABLE appointments (
    id CHAR(26) PRIMARY KEY,
    doctor_id CHAR(26) NOT NULL REFERENCES users(id),
    patient_id CHAR(26) NOT NULL REFERENCES users(id),
    created_by_id CHAR(26) NOT NULL REFERENCES users(id),
    starts_at TIMESTAMPTZ NOT NULL,
    ends_at TIMESTAMPTZ NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'scheduled',
    reason VARCHAR(500),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT ck_appointments_time CHECK (starts_at < ends_at),
    CONSTRAINT ck_appointments_status CHECK (
        status IN ('scheduled', 'cancelled', 'completed')
    )
);

CREATE INDEX ix_appointments_doctor_id ON appointments (doctor_id);
CREATE INDEX ix_appointments_patient_id ON appointments (patient_id);
CREATE INDEX ix_appointments_starts_at ON appointments (starts_at);
CREATE INDEX ix_appointments_ends_at ON appointments (ends_at);

CREATE EXTENSION IF NOT EXISTS btree_gist;

ALTER TABLE appointments
ADD CONSTRAINT ex_appointments_doctor_overlap
EXCLUDE USING gist (
    doctor_id WITH =,
    tstzrange(starts_at, ends_at, '[)') WITH &&
)
WHERE (status = 'scheduled');
