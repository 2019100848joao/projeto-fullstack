DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM user_documents GROUP BY user_id HAVING count(*) > 1
    ) THEN
        RAISE EXCEPTION 'Cannot restore one document per user while users have multiple documents';
    END IF;
END $$;

ALTER TABLE user_documents
DROP CONSTRAINT IF EXISTS uq_user_documents_user_type;

ALTER TABLE user_documents
ADD CONSTRAINT user_documents_user_id_key UNIQUE (user_id);

DROP INDEX IF EXISTS ux_user_documents_type_value;

ALTER TABLE user_documents
DROP CONSTRAINT IF EXISTS ck_user_documents_value_not_blank;

DROP INDEX IF EXISTS ux_document_type_normalized_type;

ALTER TABLE document_type
DROP CONSTRAINT IF EXISTS ck_document_type_not_blank;