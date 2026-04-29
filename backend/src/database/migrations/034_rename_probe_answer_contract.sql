UPDATE learning_questions
SET answer_kind = 'latex'
WHERE answer_kind = 'math_latex';

UPDATE assistant_active_probes
SET answer_kind = 'latex'
WHERE answer_kind = 'math_latex';

UPDATE learning_questions
SET question_payload = question_payload - 'inputKind' || jsonb_build_object('answerKind', question_payload->'inputKind')
WHERE question_payload ? 'inputKind';

UPDATE learning_questions
SET question_payload = jsonb_set(question_payload, '{answerKind}', '"latex"'::jsonb, true)
WHERE question_payload->>'answerKind' = 'math_latex';

UPDATE learning_questions
SET expected_payload = expected_payload - 'answerKind' - 'expectedAnswer' - 'probeFamily'
WHERE grade_kind = 'practice_answer';

UPDATE lessons
SET content = replace(content, 'answerKind="math_latex"', 'answerKind="latex"')
WHERE strpos(content, 'answerKind="math_latex"') > 0;

UPDATE lesson_versions
SET content = replace(content, 'answerKind="math_latex"', 'answerKind="latex"')
WHERE strpos(content, 'answerKind="math_latex"') > 0;
