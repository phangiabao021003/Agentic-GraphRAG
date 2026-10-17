-- created_at is not a reliable ordering key: rows inserted in one transaction share
-- the same now(), and ids are random UUIDs. seq gives messages a total order.
ALTER TABLE messages ADD COLUMN seq bigint GENERATED ALWAYS AS IDENTITY;
CREATE INDEX idx_messages_conversation_id_seq ON messages (conversation_id, seq);
