-- Removes only the rows this migration inserted, and only while no user
-- document references them (user_documents.type_id is ON DELETE RESTRICT).
DELETE FROM document_type
WHERE id IN ('01M8FKT4B8NB5A64JEVFGT0531', '01M8FKT4B8KS4W9ZWERVYGS2PV')
  AND NOT EXISTS (
      SELECT 1 FROM user_documents WHERE user_documents.type_id = document_type.id
  );
