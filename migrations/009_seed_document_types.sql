-- Basic document types the patient profile asks for.
-- Skips a type that already exists under any casing or spacing, so databases
-- that registered them by hand keep their rows (and the documents pointing to them).
INSERT INTO document_type (id, type)
VALUES
    ('01M8FKT4B8NB5A64JEVFGT0531', 'CPF'),
    ('01M8FKT4B8KS4W9ZWERVYGS2PV', 'RG')
ON CONFLICT ((lower(btrim(type)))) DO NOTHING;
