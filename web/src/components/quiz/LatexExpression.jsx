import "mathlive"

import { useCallback, useEffect, useMemo, useRef, useState } from "react"
import { QuizMarkdown } from "@/components/quiz/QuizMarkdown.jsx"

const normalizeHints = (hints) => {
	if (!hints) {
		return []
	}
	if (Array.isArray(hints)) {
		return hints.filter(Boolean).map((hint) => String(hint))
	}
	return [String(hints)]
}

const readLatexFieldValue = (field) => {
	if (!field) {
		return ""
	}
	if (typeof field.getValue === "function") {
		return field.getValue("latex")
	}
	return field.value || ""
}

const setLatexFieldValue = (field, value) => {
	if (!field) {
		return
	}
	if (typeof field.setValue === "function") {
		field.setValue(value)
		return
	}
	field.value = value
}

const getLatexFieldErrors = (field) => {
	if (!field || !("errors" in field)) {
		return []
	}
	const errors = field.errors
	return Array.isArray(errors) ? errors : []
}

function ReadOnlyLatexField({ latex, className }) {
	const fieldRef = useRef(null)

	useEffect(() => {
		const field = fieldRef.current
		if (!field) {
			return
		}
		setLatexFieldValue(field, latex)
		field.readOnly = true
	}, [latex])

	return <math-field ref={fieldRef} className={className} aria-label="Solution" />
}

export function LatexExpression({
	question,
	expectedLatex,
	criteria,
	hints,
	solutionLatex,
	solutionMdx,
	practiceContext = "inline",
	onGrade,
	onSkip,
	onComplete,
}) {
	const [answerLatex, setAnswerLatex] = useState("")
	const [feedback, setFeedback] = useState(null)
	const [skipFeedback, setSkipFeedback] = useState(null)
	const [attemptCount, setAttemptCount] = useState(0)
	const [revealedHints, setRevealedHints] = useState(0)
	const [isComplete, setIsComplete] = useState(false)
	const [isSolutionOpen, setIsSolutionOpen] = useState(false)
	const [isSubmitting, setIsSubmitting] = useState(false)
	const [submissionError, setSubmissionError] = useState(null)
	const fieldRef = useRef(null)
	const startedAtRef = useRef(null)

	const normalizedHints = useMemo(() => normalizeHints(hints), [hints])
	const hasHints = normalizedHints.length > 0

	const startTimer = useCallback(() => {
		if (!startedAtRef.current) {
			startedAtRef.current = Date.now()
		}
	}, [])

	const getDurationMs = useCallback(() => {
		if (!startedAtRef.current) {
			return 0
		}
		return Math.max(0, Date.now() - startedAtRef.current)
	}, [])

	const resetState = useCallback(() => {
		setAnswerLatex("")
		setFeedback(null)
		setSkipFeedback(null)
		setAttemptCount(0)
		setRevealedHints(0)
		setIsComplete(false)
		setIsSolutionOpen(false)
		setSubmissionError(null)
		setIsSubmitting(false)
		startedAtRef.current = null
		setLatexFieldValue(fieldRef.current, "")
	}, [])

	useEffect(() => {
		const field = fieldRef.current
		if (!field) {
			return
		}

		const handleInput = () => {
			startTimer()
			setAnswerLatex(readLatexFieldValue(field))
		}

		field.addEventListener("input", handleInput)
		return () => {
			field.removeEventListener("input", handleInput)
		}
	}, [startTimer])

	useEffect(() => {
		const field = fieldRef.current
		if (!field) {
			return
		}
		field.readOnly = isSubmitting || isComplete
	}, [isComplete, isSubmitting])

	const handleSubmit = useCallback(async () => {
		if (isSubmitting || isComplete) {
			return
		}

		const trimmedAnswer = answerLatex.trim()
		if (!trimmedAnswer) {
			return
		}

		setSubmissionError(null)
		const syntaxErrors = getLatexFieldErrors(fieldRef.current)
		if (syntaxErrors.length > 0) {
			setSubmissionError("Fix the LaTeX syntax before submitting.")
			return
		}

		if (typeof onGrade !== "function") {
			setSubmissionError("Grading is unavailable right now.")
			return
		}

		setIsSubmitting(true)
		setSubmissionError(null)
		startTimer()

		const nextAttempt = attemptCount + 1
		setAttemptCount(nextAttempt)

		try {
			const result = await onGrade({
				question,
				expectedLatex,
				criteria,
				answerLatex: trimmedAnswer,
				practiceContext,
				attempts: nextAttempt,
				hintsUsed: revealedHints,
				durationMs: getDurationMs(),
			})

			const grade = result?.grade ?? result
			setFeedback(grade ?? null)
			setSkipFeedback(null)

			if (grade?.isCorrect) {
				setIsComplete(true)
				onComplete?.(result)
			}
		} catch (err) {
			setSubmissionError(err?.message || "Unable to submit your answer. Please try again.")
		} finally {
			setIsSubmitting(false)
		}
	}, [
		answerLatex,
		attemptCount,
		criteria,
		expectedLatex,
		getDurationMs,
		isComplete,
		isSubmitting,
		onComplete,
		onGrade,
		practiceContext,
		question,
		revealedHints,
		startTimer,
	])

	const handleSkip = useCallback(async () => {
		if (isSubmitting || isComplete) {
			return
		}

		if (typeof onSkip !== "function") {
			setSubmissionError("Skip is unavailable right now.")
			return
		}

		setIsSubmitting(true)
		setSubmissionError(null)
		startTimer()

		try {
			const result = await onSkip({
				question,
				expectedLatex,
				criteria,
				practiceContext,
				attempts: attemptCount || 1,
				hintsUsed: revealedHints,
				durationMs: getDurationMs(),
			})
			setFeedback(null)
			setSkipFeedback("No worries — review the hints or solution, then try another question.")
			setIsComplete(true)
			setIsSolutionOpen(true)
			onComplete?.({ ...result, skipped: true })
		} catch (err) {
			setSubmissionError(err?.message || "Unable to skip this question right now.")
		} finally {
			setIsSubmitting(false)
		}
	}, [
		attemptCount,
		criteria,
		expectedLatex,
		getDurationMs,
		isComplete,
		isSubmitting,
		onComplete,
		onSkip,
		practiceContext,
		question,
		revealedHints,
		startTimer,
	])

	const handleRevealHint = useCallback(() => {
		setRevealedHints((value) => Math.min(value + 1, normalizedHints.length))
	}, [normalizedHints.length])

	const handleSolutionToggle = useCallback((event) => {
		setIsSolutionOpen(event.currentTarget.open)
	}, [])

	const canSubmit = answerLatex.trim().length > 0 && !isSubmitting && !isComplete

	let feedbackTitle = null
	let feedbackTone = "text-muted-foreground"
	let feedbackContainer = "border-border bg-muted/20"
	let feedbackMessage = null

	if (feedback) {
		feedbackMessage = feedback.feedbackMarkdown
		if (feedback.isCorrect) {
			feedbackTitle = "✓ Correct"
			feedbackTone = "text-completed"
			feedbackContainer = "border-completed/30 bg-completed/10"
		} else if (feedback.status === "parse_error") {
			feedbackTitle = "Check the LaTeX"
			feedbackTone = "text-amber-600"
			feedbackContainer = "border-amber-400/40 bg-amber-50/70"
		} else {
			feedbackTitle = "Not quite"
			feedbackTone = "text-destructive"
			feedbackContainer = "border-destructive/30 bg-destructive/10"
		}
	} else if (skipFeedback) {
		feedbackTitle = "Let’s walk through it"
		feedbackTone = "text-amber-700"
		feedbackContainer = "border-amber-400/40 bg-amber-50/70"
		feedbackMessage = skipFeedback
	}

	const showFeedback = Boolean(feedbackMessage)
	const showSolution = Boolean(solutionLatex || solutionMdx)

	return (
		<div className="border-l-4 border-l-completed/20 pl-6 my-8 bg-background/30 rounded-r-lg" data-askai-exclude="true">
			<QuizMarkdown content={question} className="mb-4 text-lg font-medium text-foreground [&_p]:m-0" />

			<div className="mb-4">
				<div className="text-xs uppercase tracking-wide text-muted-foreground mb-2">Your answer</div>
				<div className="rounded-lg border border-input bg-background px-3 py-2 focus-within:ring-2 focus-within:ring-ring">
					<math-field
						ref={fieldRef}
						className="w-full min-h-[2.75rem] text-base text-foreground"
						aria-label="Expression answer input"
					/>
				</div>
			</div>

			{submissionError ? (
				<div className="mb-4 rounded-lg border border-destructive/40 bg-destructive/10 px-4 py-3 text-sm text-destructive">
					{submissionError}
				</div>
			) : null}

			{showFeedback ? (
				<div className={`mb-4 rounded-lg border px-4 py-3 ${feedbackContainer}`}>
					{feedbackTitle ? <div className={`text-sm font-medium mb-2 ${feedbackTone}`}>{feedbackTitle}</div> : null}
					{feedbackMessage ? (
						<QuizMarkdown
							content={feedbackMessage}
							className="text-sm leading-relaxed text-muted-foreground [&_p]:m-0"
						/>
					) : null}
					{feedback?.errorHighlight?.latex ? (
						<div className="mt-3 rounded-md border border-amber-400/40 bg-amber-50/70 px-3 py-2">
							<div className="text-xs font-semibold uppercase tracking-wide text-amber-700 mb-2">Check this part</div>
							<ReadOnlyLatexField
								latex={feedback.errorHighlight.latex}
								className="w-full min-h-[2.25rem] bg-background/80 rounded-md px-2 py-1"
							/>
						</div>
					) : null}
				</div>
			) : null}

			<div className="flex flex-wrap items-center gap-2 mb-4">
				{!isComplete ? (
					<>
						<button
							type="button"
							onClick={handleSubmit}
							disabled={!canSubmit}
							className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
								canSubmit
									? "bg-completed text-completed-text hover:bg-completed/90"
									: "bg-muted text-muted-foreground cursor-not-allowed"
							}`}
						>
							Check Answer
						</button>
						<button
							type="button"
							onClick={handleSkip}
							disabled={isSubmitting}
							className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
								isSubmitting
									? "bg-muted text-muted-foreground cursor-not-allowed"
									: "bg-muted text-foreground hover:bg-muted/80"
							}`}
						>
							I don&apos;t know
						</button>
					</>
				) : (
					<button
						type="button"
						onClick={resetState}
						className="px-4 py-2 rounded-lg text-sm font-medium transition-colors bg-muted text-foreground hover:bg-muted/80"
					>
						Try another
					</button>
				)}
			</div>

			{hasHints ? (
				<div className="mb-4">
					<div className="flex items-center gap-2 mb-2">
						<span className="text-xs uppercase tracking-wide text-muted-foreground">Hints</span>
						{revealedHints < normalizedHints.length ? (
							<button
								type="button"
								onClick={handleRevealHint}
								className="text-xs font-medium text-primary hover:text-primary/80"
							>
								Show next hint
							</button>
						) : null}
					</div>
					{revealedHints > 0 ? (
						<ul className="space-y-2 text-sm text-muted-foreground">
							{normalizedHints.slice(0, revealedHints).map((hint) => (
								<li key={`${question}-${hint}`} className="rounded-md border border-border/60 bg-muted/30 px-3 py-2">
									<QuizMarkdown content={hint} className="[&_p]:m-0" />
								</li>
							))}
						</ul>
					) : (
						<p className="text-sm text-muted-foreground">Hints are available when you need them.</p>
					)}
				</div>
			) : null}

			{showSolution ? (
				<details className="group" open={isSolutionOpen} onToggle={handleSolutionToggle}>
					<summary className="cursor-pointer text-sm font-medium text-foreground">View solution</summary>
					<div className="mt-3 space-y-3 rounded-lg border border-border/60 bg-muted/20 p-4">
						{solutionLatex ? (
							<ReadOnlyLatexField
								latex={solutionLatex}
								className="w-full min-h-[2.5rem] bg-background/80 rounded-md px-2 py-1"
							/>
						) : null}
						{solutionMdx ? (
							<QuizMarkdown content={solutionMdx} className="text-sm leading-relaxed text-muted-foreground [&_p]:m-0" />
						) : null}
					</div>
				</details>
			) : null}
		</div>
	)
}
