import { useCallback, useMemo, useRef, useState } from "react"
import { Button } from "@/components/Button"
import { JXGBoard } from "@/components/JXGBoard.jsx"
import { useLatexPracticeReview } from "../hooks/useLatexPracticeReview.js"

const isObjectRecord = (value) => {
	return Boolean(value) && typeof value === "object" && !Array.isArray(value)
}

const toFiniteNumber = (value) => {
	const parsed = Number(value)
	if (!Number.isFinite(parsed)) {
		return null
	}
	return parsed
}

const normalizePoints = (value) => {
	if (!isObjectRecord(value)) {
		return {}
	}

	const points = {}
	for (const [id, coords] of Object.entries(value)) {
		if (!Array.isArray(coords) || coords.length !== 2) {
			continue
		}
		const x = toFiniteNumber(coords[0])
		const y = toFiniteNumber(coords[1])
		if (x === null || y === null) {
			continue
		}
		points[id] = [x, y]
	}
	return points
}

const normalizeSliders = (value) => {
	if (!isObjectRecord(value)) {
		return {}
	}

	const sliders = {}
	for (const [id, rawValue] of Object.entries(value)) {
		const parsed = toFiniteNumber(rawValue)
		if (parsed === null) {
			continue
		}
		sliders[id] = parsed
	}
	return sliders
}

const normalizeCurves = (value) => {
	if (!isObjectRecord(value)) {
		return {}
	}

	const curves = {}
	for (const [id, rawSamples] of Object.entries(value)) {
		if (!Array.isArray(rawSamples)) {
			continue
		}

		const samples = []
		for (const sample of rawSamples) {
			if (!Array.isArray(sample) || sample.length !== 2) {
				continue
			}
			const x = toFiniteNumber(sample[0])
			const y = toFiniteNumber(sample[1])
			if (x === null || y === null) {
				continue
			}
			samples.push([x, y])
		}

		curves[id] = samples
	}
	return curves
}

const normalizeJxgState = (payload) => {
	if (!isObjectRecord(payload)) {
		return null
	}
	return {
		points: normalizePoints(payload.points),
		sliders: normalizeSliders(payload.sliders),
		curves: normalizeCurves(payload.curves),
	}
}

export function JXGBoardPractice({
	question = "Match the target board state.",
	expectedState = null,
	tolerance,
	perCheckTolerance,
	criteria,
	practiceContext = "inline",
	courseId,
	lessonId,
	lessonConceptId,
	conceptId,
	stateEventName = "state",
	onEvent,
	onComplete,
	...boardProps
}) {
	const resolvedConceptId = conceptId ?? lessonConceptId ?? null
	const normalizedExpectedState = useMemo(() => normalizeJxgState(expectedState), [expectedState])
	const hasGradingConfig = Boolean(normalizedExpectedState && courseId && lessonId && resolvedConceptId)
	const [answerState, setAnswerState] = useState(null)
	const [lastGrade, setLastGrade] = useState(null)
	const [attempts, setAttempts] = useState(0)
	const interactionStartRef = useRef(null)

	const { submitJxgStateAnswer, isSubmitting, error } = useLatexPracticeReview({
		courseId,
		lessonId,
		conceptId: resolvedConceptId,
		practiceContext,
	})

	const handleBoardEvent = useCallback(
		(event) => {
			if (typeof onEvent === "function") {
				onEvent(event)
			}
			if (!hasGradingConfig) {
				return
			}
			if (event?.name !== stateEventName) {
				return
			}
			const normalizedState = normalizeJxgState(event?.payload)
			if (!normalizedState) {
				return
			}

			if (interactionStartRef.current === null) {
				interactionStartRef.current = Date.now()
			}
			setAnswerState(normalizedState)
		},
		[hasGradingConfig, onEvent, stateEventName]
	)

	const handleSubmit = useCallback(async () => {
		if (!hasGradingConfig || !isObjectRecord(answerState)) {
			return
		}

		if (interactionStartRef.current === null) {
			interactionStartRef.current = Date.now()
		}

		const nextAttempts = attempts + 1
		setAttempts(nextAttempts)
		const durationMs = Date.now() - interactionStartRef.current

		const result = await submitJxgStateAnswer({
			question,
			expectedState: normalizedExpectedState,
			answerState,
			tolerance,
			perCheckTolerance,
			criteria,
			conceptId: resolvedConceptId,
			attempts: nextAttempts,
			durationMs,
			hintsUsed: 0,
			practiceContext,
		})

		setLastGrade(result?.grade ?? null)
		if (typeof onComplete === "function" && result?.grade) {
			onComplete(result.grade)
		}
	}, [
		answerState,
		attempts,
		criteria,
		hasGradingConfig,
		onComplete,
		perCheckTolerance,
		practiceContext,
		question,
		resolvedConceptId,
		submitJxgStateAnswer,
		tolerance,
		normalizedExpectedState,
	])

	if (!hasGradingConfig) {
		return <JXGBoard {...boardProps} onEvent={onEvent} />
	}

	const statusText = answerState ? "Board state captured." : `Waiting for "${stateEventName}" event payload...`
	const feedbackText = lastGrade?.feedbackMarkdown ?? ""
	const showFeedback = Boolean(feedbackText)
	const isCorrect = lastGrade?.isCorrect === true

	return (
		<div className="space-y-3">
			<JXGBoard {...boardProps} onEvent={handleBoardEvent} />
			<div className="rounded-lg border border-border/60 bg-card/70 p-3">
				<p className="text-sm text-muted-foreground">{statusText}</p>
				<div className="mt-3 flex items-center justify-end">
					<Button type="button" onClick={handleSubmit} disabled={!answerState || isSubmitting}>
						{isSubmitting ? "Checking..." : "Check board state"}
					</Button>
				</div>
				{error ? (
					<p className="mt-2 text-sm text-destructive">{error.message ?? "Failed to grade board state."}</p>
				) : null}
				{showFeedback ? (
					<p className={`mt-2 text-sm ${isCorrect ? "text-completed" : "text-foreground"}`}>{feedbackText}</p>
				) : null}
			</div>
		</div>
	)
}

export default JXGBoardPractice
