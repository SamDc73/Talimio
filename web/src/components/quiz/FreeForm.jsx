import "mathlive"

import { useEffect, useRef, useState } from "react"
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

export function FreeForm({ questionId, question, answerKind = "text", courseId, lessonId, lessonConceptId }) {
	const courseService = useCourseService(courseId)
	const fieldRef = useRef(null)
	const [userAnswer, setUserAnswer] = useState("")
	const [grade, setGrade] = useState(null)
	const [isSubmitting, setIsSubmitting] = useState(false)
	const [submissionError, setSubmissionError] = useState(null)

	const isMathLatex = answerKind === "math_latex"
	const submitted = grade !== null
	const hasGradingContext = Boolean(courseId && lessonId && lessonConceptId && questionId)
	const hasAnswer = userAnswer.trim().length > 0

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
		if (isSubmitting || submitted || !hasAnswer || !hasGradingContext) {
			return
		}

		if (isMathLatex && getMathFieldErrors(fieldRef.current).length > 0) {
			setSubmissionError("Fix the LaTeX syntax before submitting.")
			return
		}

		setIsSubmitting(true)
		setSubmissionError(null)

		try {
			const trimmedAnswer = userAnswer.trim()
			const response = await courseService.submitAttempt({
				attemptId: crypto.randomUUID(),
				questionId,
				answer:
					answerKind === "math_latex"
						? { kind: "math_latex", answerLatex: trimmedAnswer }
						: { kind: "text", answerText: trimmedAnswer },
				hintsUsed: 0,
				durationMs: 0,
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
				{!submitted && !hasGradingContext && (
					<div className="mt-2 text-xs text-muted-foreground">
						<span className="text-destructive">This question is missing the grading data needed for submission.</span>
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

					<button type="button" onClick={handleReset} className={QUIZ_RESET_BUTTON_CLASS_NAME}>
						Write Another Answer
					</button>
				</div>
			) : (
				<button
					type="button"
					onClick={handleSubmit}
					disabled={!hasAnswer || !hasGradingContext || isSubmitting}
					className={`${
						!hasAnswer || !hasGradingContext || isSubmitting
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
