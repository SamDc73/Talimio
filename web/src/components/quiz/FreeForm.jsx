import "mathlive"

import { useEffect, useMemo, useRef, useState } from "react"
import { useCourseService } from "@/api/courseApi"
import { QuizMarkdown } from "@/components/quiz/QuizMarkdown"
import {
	QUIZ_ACTIVE_BUTTON_CLASS_NAME,
	QUIZ_DISABLED_BUTTON_CLASS_NAME,
	QUIZ_ERROR_PANEL_CLASS_NAME,
	QUIZ_RESET_BUTTON_CLASS_NAME,
	QUIZ_SUCCESS_PANEL_CLASS_NAME,
	QUIZ_WIDGET_CLASS_NAME,
} from "@/components/quiz/quizUiClassNames"
import { cn } from "@/lib/utils"

const readMathFieldValue = (field) => {
	if (!field) {
		return ""
	}
	if (typeof field.getValue === "function") {
		return field.getValue("latex")
	}
	return field.value || ""
}

const setMathFieldValue = (field, value) => {
	if (!field) {
		return
	}
	if (typeof field.setValue === "function") {
		field.setValue(value)
		return
	}
	field.value = value
}

const getMathFieldErrors = (field) => {
	if (!field || !("errors" in field)) {
		return []
	}
	const errors = field.errors
	return Array.isArray(errors) ? errors : []
}

export function FreeForm({
	question,
	expectedAnswer,
	sampleAnswer,
	answerKind = "text",
	minLength = 50,
	courseId,
	lessonId,
	lessonConceptId,
}) {
	const courseService = useCourseService(courseId)
	const fieldRef = useRef(null)
	const [userAnswer, setUserAnswer] = useState("")
	const [grade, setGrade] = useState(null)
	const [isSubmitting, setIsSubmitting] = useState(false)
	const [submissionError, setSubmissionError] = useState(null)

	const resolvedExpectedAnswer = useMemo(() => {
		if (typeof expectedAnswer === "string" && expectedAnswer.trim()) {
			return expectedAnswer.trim()
		}
		if (typeof sampleAnswer === "string" && sampleAnswer.trim()) {
			return sampleAnswer.trim()
		}
		return ""
	}, [expectedAnswer, sampleAnswer])

	const isMathLatex = answerKind === "math_latex"
	const submitted = grade !== null
	const hasGradingContext = Boolean(courseId && lessonId && lessonConceptId && resolvedExpectedAnswer)
	const remainingChars = Math.max(0, minLength - userAnswer.length)
	let guidanceMessage = `Please write at least ${remainingChars} more characters`
	let guidanceClassName = "text-due-today"

	if (!hasGradingContext) {
		guidanceMessage = "This question is missing the grading data needed for submission."
		guidanceClassName = "text-destructive"
	} else if (remainingChars === 0) {
		guidanceMessage = `✓ Minimum length reached (${userAnswer.length} characters)`
		guidanceClassName = "text-completed"
	}

	useEffect(() => {
		if (!isMathLatex) {
			return
		}

		const field = fieldRef.current
		if (!field) {
			return
		}

		const handleInput = () => {
			setUserAnswer(readMathFieldValue(field))
		}

		field.addEventListener("input", handleInput)
		return () => {
			field.removeEventListener("input", handleInput)
		}
	}, [isMathLatex])

	useEffect(() => {
		if (!isMathLatex || !fieldRef.current) {
			return
		}

		fieldRef.current.readOnly = submitted || isSubmitting
	}, [isMathLatex, isSubmitting, submitted])

	const handleSubmit = async () => {
		if (isSubmitting || submitted || userAnswer.length < minLength || !hasGradingContext) {
			return
		}

		if (isMathLatex && getMathFieldErrors(fieldRef.current).length > 0) {
			setSubmissionError("Fix the LaTeX syntax before submitting.")
			return
		}

		setIsSubmitting(true)
		setSubmissionError(null)

		try {
			const response = await courseService.gradeLessonAnswer(lessonId, {
				kind: "practice_answer",
				question,
				expected: {
					expectedAnswer: resolvedExpectedAnswer,
					answerKind,
				},
				answer: {
					answerText: userAnswer.trim(),
				},
				context: {
					courseId,
					lessonId,
					conceptId: lessonConceptId,
					practiceContext: "inline",
					hintsUsed: 0,
				},
			})

			setGrade(response)
		} catch (error) {
			setSubmissionError(error?.message || "Unable to grade your answer right now. Please try again.")
		} finally {
			setIsSubmitting(false)
		}
	}

	const handleReset = () => {
		setUserAnswer("")
		setGrade(null)
		setSubmissionError(null)
		setIsSubmitting(false)
		if (isMathLatex) {
			setMathFieldValue(fieldRef.current, "")
		}
	}

	return (
		<div className={QUIZ_WIDGET_CLASS_NAME} data-askai-exclude="true">
			<QuizMarkdown content={question} className="mb-6 text-lg font-medium text-foreground [&_p]:m-0" />

			<div className="mb-6">
				{isMathLatex ? (
					<math-field
						ref={fieldRef}
						aria-label="Type your answer here..."
						className={`block w-full min-h-28 px-4 py-3 text-sm rounded-lg border transition-all focus:ring-2 focus:ring-ring focus:outline-none ${
							submitted
								? "bg-completed/10 border-completed/30 text-completed dark:bg-completed/20 dark:border-completed/30 dark:text-completed"
								: "bg-background border-input focus:border-ring"
						}`}
					/>
				) : (
					<textarea
						value={userAnswer}
						onChange={(e) => !submitted && !isSubmitting && setUserAnswer(e.target.value)}
						disabled={submitted || isSubmitting}
						placeholder="Type your answer here..."
						rows={4}
						className={`w-full px-4 py-3 text-sm rounded-lg border resize-y transition-all focus:ring-2 focus:ring-ring focus:outline-none placeholder:text-muted-foreground/70 ${
							submitted
								? "bg-completed/10 border-completed/30 text-completed dark:bg-completed/20 dark:border-completed/30 dark:text-completed"
								: "bg-background border-input focus:border-ring"
						}`}
					/>
				)}
				{!submitted && (
					<div className="mt-2 text-xs text-muted-foreground">
						<span className={guidanceClassName}>{guidanceMessage}</span>
					</div>
				)}
				{submissionError && !submitted && (
					<div className={cn(QUIZ_ERROR_PANEL_CLASS_NAME, "mt-3 px-4 py-3 text-sm text-destructive")}>
						{submissionError}
					</div>
				)}
			</div>

			{submitted ? (
				<div>
					<div className={cn(QUIZ_SUCCESS_PANEL_CLASS_NAME, "mb-4 p-4")}>
						<div className="text-sm font-medium mb-2 text-completed">✓ Answer Submitted</div>

						<QuizMarkdown
							content={grade.feedbackMarkdown}
							className="text-sm/relaxed text-muted-foreground [&_p]:m-0"
						/>
					</div>

					{sampleAnswer && (
						<details className="mb-4 group">
							<summary className="cursor-pointer p-4 rounded-lg border border-border bg-background hover:bg-muted/30 transition-colors">
								<span className="text-sm font-medium text-foreground group-open:text-primary">View Sample Answer</span>
							</summary>
							<div className="mt-3 p-4 rounded-lg bg-muted/20 border border-border">
								<QuizMarkdown content={sampleAnswer} className="text-sm/relaxed  text-muted-foreground [&_p]:m-0" />
							</div>
						</details>
					)}

					<button type="button" onClick={handleReset} className={QUIZ_RESET_BUTTON_CLASS_NAME}>
						Write Another Answer
					</button>
				</div>
			) : (
				<button
					type="button"
					onClick={handleSubmit}
					disabled={userAnswer.length < minLength || !hasGradingContext || isSubmitting}
					className={`${
						userAnswer.length < minLength || !hasGradingContext || isSubmitting
							? QUIZ_DISABLED_BUTTON_CLASS_NAME
							: QUIZ_ACTIVE_BUTTON_CLASS_NAME
					}`}
				>
					{isSubmitting ? "Submitting..." : "Submit Answer"}
				</button>
			)}
		</div>
	)
}
