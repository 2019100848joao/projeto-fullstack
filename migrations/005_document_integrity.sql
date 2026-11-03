ALTER TABLE document_type
ADD CONSTRAINT ck_document_type_not_blank CHECK (btrim(type) <> '');

CREATE UNIQUE INDEX ux_document_type_normalized_type
ON document_type (lower(btrim(type)));

ALTER TABLE user_documents
ADD CONSTRAINT ck_user_documents_value_not_blank
CHECK (regexp_replace(value, '[^[:alnum:]]', '', 'g') <> '');

CREATE UNIQUE INDEX ux_user_documents_type_value
ON user_documents (
    type_id,
    lower(regexp_replace(value, '[^[:alnum:]]', '', 'g'))
);

ALTER TABLE user_documents
DROP CONSTRAINT user_documents_user_id_key;

ALTER TABLE user_documents
ADD CONSTRAINT uq_user_documents_user_type UNIQUE (user_id, type_id);
