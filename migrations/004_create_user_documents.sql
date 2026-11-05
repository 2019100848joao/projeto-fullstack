CREATE TABLE user_documents (
    id CHAR(26) PRIMARY KEY,
    user_id CHAR(26) NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
    value VARCHAR(255) NOT NULL,
    type_id CHAR(26) NOT NULL REFERENCES document_type(id) ON DELETE CASCADE
);

CREATE INDEX ix_user_documents_user_id ON user_documents (user_id);
CREATE INDEX ix_user_documents_type_id ON user_documents (type_id);
