-- mem0 cutover: canonical profile slots replaced the mem0 store.
-- learning_memories was verified empty before this migration shipped.

DROP TABLE IF EXISTS learning_memories;
DROP TABLE IF EXISTS mem0migrations;
