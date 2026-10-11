ALTER TABLE appointments
DROP CONSTRAINT IF EXISTS ex_appointments_doctor_overlap;

DROP TABLE IF EXISTS appointments;
