UPDATE appointments SET status = 'scheduled' WHERE status = 'no_show';

ALTER TABLE appointments DROP CONSTRAINT ck_appointments_status;

ALTER TABLE appointments
ADD CONSTRAINT ck_appointments_status
CHECK (status IN ('scheduled', 'cancelled', 'completed'));
