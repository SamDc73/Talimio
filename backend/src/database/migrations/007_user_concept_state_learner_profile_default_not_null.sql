-- 007_user_concept_state_learner_profile_default_not_null.sql
-- Ensure learner_profile has a server-side default and NOT NULL to support bulk inserts
-- and align with ORM expectations across environments.

ALTER TABLE user_concept_state
    ALTER COLUMN learner_profile SET DEFAULT '{"success_rate": 0.5, "learning_speed": 1.0, "retention_rate": 0.8, "semantic_sensitivity": 1.0}'::jsonb;

UPDATE user_concept_state
SET learner_profile = '{"success_rate": 0.5, "learning_speed": 1.0, "retention_rate": 0.8, "semantic_sensitivity": 1.0}'::jsonb
WHERE learner_profile IS NULL;

ALTER TABLE user_concept_state
    ALTER COLUMN learner_profile SET NOT NULL;
