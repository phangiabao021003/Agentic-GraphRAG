CREATE TABLE messages (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id uuid NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    role text NOT NULL CHECK (role IN ('user', 'assistant')),
    content text NOT NULL,
    tool_calls jsonb,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX idx_messages_conversation_id_created_at ON messages (conversation_id, created_at);
