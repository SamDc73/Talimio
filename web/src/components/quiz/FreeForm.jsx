import { useMemo, useState } from "react"
import { useCourseService } from "@/api/courseApi"
import { QuizMarkdown } from "@/components/quiz/QuizMarkdown"

export function FreeForm({
	question,
	expectedAnswer,
	sampleAnswer,
	minLength = 50,
	courseId,
	lessonId,
	lessonConceptId,
}) {
	const courseService = useCourseService(courseId)
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

	const submitted = grade !== null
	const hasGradingContext = Boolean(courseId && lessonId && lessonConceptId && resolvedExpectedAnswer)
	const remainingChars = Math.max(0, minLength - userAnswer.length)
	let guidanceMessage = `Please write at least ${remainingChars} more characters`
	let guidanceClassName = "text-due-today"

	if (!hasGradingContext) {
		guidanceMessage = "This question is missing the grading data needed for submission."
	} else if (remainingChars === 0) {
		guidanceMessage = `✓ Minimum length reached (${userAnswer.length} characters)`
		guidanceClassName = "text-completed"
	}

	const handleSubmit = async () => {
		if (isSubmitting || submitted || userAnswer.length < minLength || !hasGradingContext) {
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
					answerKind: "text",
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
	}

	return (
		<div className="border-l-4 border-l-completed/20 pl-6 my-8 bg-background/30 rounded-r-lg" data-askai-exclude="true">
			<QuizMarkdown content={question} className="mb-6 text-lg font-medium text-foreground [&_p]:m-0" />

			<div className="mb-6">
				<textarea
					value={userAnswer}
					onChange={(e) => !submitted && !isSubmitting && setUserAnswer(e.target.value)}
					disabled={submitted || isSubmitting}
					placeholder="Type your answer here..."
					rows={4}
					className={`w-full px-4 py-3 text-sm rounded-lg border resize-y transition-all focus:ring-2 focus:ring-ring focus:outline-none placeholder:text-muted-foreground/70 ${
						submitted
							? "bg-completed/10 border-completed/30 text-completed dark:bg-completed/20 dark:border-completed/30 dark:text-completed"
							: "bg-background border-input focus:border-completed/40"
					}`}
				/>
				{!submitted && (
					<div className="mt-2 text-xs text-muted-foreground">
						<span className={guidanceClassName}>{guidanceMessage}</span>
					</div>
				)}
				{submissionError && !submitted && (
					<div className="mt-3 rounded-lg border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive">
						{submissionError}
					</div>
				)}
			</div>

			{submitted ? (
				<div>
					<div className="p-4 mb-4 rounded-lg border border-border bg-muted/20">
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

					<button
						type="button"
						onClick={handleReset}
						className="px-4 py-2 bg-muted text-foreground hover:bg-muted/80 rounded-lg text-sm font-medium transition-colors"
					>
						Write Another Answer
					</button>
				</div>
			) : (
				<button
					type="button"
					onClick={handleSubmit}
					disabled={userAnswer.length < minLength || !hasGradingContext || isSubmitting}
					className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
						userAnswer.length < minLength || !hasGradingContext || isSubmitting
							? "bg-muted text-muted-foreground cursor-not-allowed"
							: "bg-completed text-completed-text hover:bg-completed/90"
					}`}
				>
					{isSubmitting ? "Submitting..." : "Submit Answer"}
				</button>
			)}
		</div>
	)
}
