import { AnimatePresence, motion } from "framer-motion"
import { AlertCircle, Loader2 } from "lucide-react"
import { useCallback, useEffect, useMemo, useRef, useState } from "react"

import { Button } from "@/components/Button"
import { DialogHeader, DialogTitle } from "@/components/Dialog"
import { MultipleChoice } from "@/components/quiz/MultipleChoice"
import { useCourseService } from "./api/courseApi"

const MOTION_VARIANTS = {
	enter: { opacity: 0, x: 16 },
	center: { opacity: 1, x: 0 },
	exit: { opacity: 0, x: -16 },
}

// Simple backoff to handle occasional cold-start where first call returns nothing
const AUTO_RETRY_DELAY_MS = 1200
const MAX_AUTO_RETRIES = 2

function buildSummary(responses, questions) {
	const answered = Object.entries(responses)
		.map(([index, value]) => {
			const question = questions[Number(index)]
			if (!question || value?.optionLabel === undefined) {
				return null
			}
			return {
				question: question.question,
				answer: value.optionLabel,
			}
		})
		.filter(Boolean)

	return answered
}

export default function SelfAssessmentDialog({ topic, level = null, onBack, onSkipAll, onComplete, isSubmitting }) {
	const courseService = useCourseService()
	const [questions, setQuestions] = useState([])
	const [responses, setResponses] = useState({})
	const [currentIndex, setCurrentIndex] = useState(0)
	const [error, setError] = useState("")
	const [isLoading, setIsLoading] = useState(true)
	// Track the latest in-flight request to avoid race conditions/StrictMode double-invocation
	const requestIdRef = useRef(0)
	const autoRetryCountRef = useRef(0)
	const [isAutoRetrying, setIsAutoRetrying] = useState(false)
	const [autoRetryAttempt, setAutoRetryAttempt] = useState(0)

	const executeRef = useRef(courseService.fetchSelfAssessmentQuestions)
	executeRef.current = courseService.fetchSelfAssessmentQuestions

	const loadQuestions = useCallback(async () => {
		const myRequestId = ++requestIdRef.current
		setIsLoading(true)
		setError("")
		setResponses({})
		setCurrentIndex(0)

		let keepLoading = false
		try {
			const payload = {
				topic: topic.trim(),
			}
			if (level) {
				payload.level = level
			}

			const result = await executeRef.current(payload)

			// If this call is outdated or was aborted, ignore without flipping UI state
			if (requestIdRef.current !== myRequestId || !result) {
				return
			}

			const sanitized = Array.isArray(result?.questions) ? result.questions.slice(0, 5) : []

			if (!sanitized.length) {
				// Auto-retry a couple of times before surfacing an error
				if (autoRetryCountRef.current < MAX_AUTO_RETRIES) {
					autoRetryCountRef.current += 1
					keepLoading = true
					setIsAutoRetrying(true)
					setAutoRetryAttempt(autoRetryCountRef.current)
					setTimeout(() => {
						// Only retry if this request was the latest when scheduled
						if (requestIdRef.current === myRequestId) {
							loadQuestions()
						}
					}, AUTO_RETRY_DELAY_MS)
					return
				}

				// Exhausted retries
				setQuestions([])
				setError("No self-assessment questions were generated. You can skip this step.")
				return
			}

			setQuestions(sanitized)
			setError("")
			setIsAutoRetrying(false)
			setAutoRetryAttempt(0)
		} catch (fetchError) {
			if (requestIdRef.current !== myRequestId) return
			setQuestions([])
			setError(fetchError?.message || "Failed to load self-assessment questions.")
			setIsAutoRetrying(false)
		} finally {
			if (requestIdRef.current === myRequestId && !keepLoading) {
				setIsLoading(false)
				setIsAutoRetrying(false)
				setAutoRetryAttempt(0)
			}
		}
	}, [level, topic])

	const handleManualRetry = useCallback(() => {
		autoRetryCountRef.current = 0
		loadQuestions()
	}, [loadQuestions])

	useEffect(() => {
		loadQuestions()
	}, [loadQuestions])

	const totalSteps = useMemo(() => {
		return questions.length || 0
	}, [questions])

	const currentStepIndex = currentIndex

	const currentQuestion = questions[currentIndex]
	const currentSelection = responses[currentIndex]?.optionIndex ?? null

	const handleSelectOption = (optionIndex) => {
		if (!currentQuestion) {
			return
		}

		const optionLabel = currentQuestion.options?.[optionIndex]
		setResponses((prev) => ({
			...prev,
			[currentIndex]: {
				optionIndex,
				optionLabel,
			},
		}))
	}

	const goToNext = () => {
		if (currentIndex + 1 >= questions.length) {
			onComplete(answeredSummary)
			return
		}
		setCurrentIndex((index) => index + 1)
	}

	const goToPrevious = () => {
		if (currentIndex === 0) {
			onBack()
			return
		}
		setCurrentIndex((index) => Math.max(0, index - 1))
	}

	const handleSkip = () => {
		setResponses((prev) => {
			const next = { ...prev }
			delete next[currentIndex]
			return next
		})
		goToNext()
	}

	const answeredSummary = useMemo(() => buildSummary(responses, questions), [responses, questions])

	return (
		<div className="space-y-6">
			<DialogHeader className="space-y-3">
				<DialogTitle className="text-2xl">Self-assessment</DialogTitle>
				<p className="text-sm text-muted-foreground">
					Answer a few quick questions to tailor your course. You can skip any question.
				</p>
			</DialogHeader>

			<div className="flex items-center gap-2">
				{Array.from({ length: totalSteps }, (_, i) => ({ id: i, isActive: i <= currentStepIndex })).map(
					({ id, isActive }) => (
						<div
							key={`progress-step-${id}`}
							className={`h-1 flex-1 rounded-full ${isActive ? "bg-[var(--color-course)]" : "bg-border"}`}
						/>
					)
				)}
			</div>

			{isLoading ? (
				<div className="flex flex-col items-center justify-center py-12 text-muted-foreground">
					<Loader2 className="h-6 w-6 animate-spin" />
					<span className="mt-3 text-sm">
						{isAutoRetrying
							? `Generating questions… (attempt ${autoRetryAttempt}/${MAX_AUTO_RETRIES})`
							: "Loading questions…"}
					</span>
				</div>
			) : (
				<AnimatePresence mode="wait">
					<motion.div
						key={`question-${currentIndex}`}
						initial="enter"
						animate="center"
						exit="exit"
						variants={MOTION_VARIANTS}
						transition={{ duration: 0.2 }}
						className="space-y-4"
					>
						{currentQuestion ? (
							<MultipleChoice
								question={currentQuestion.question}
								options={currentQuestion.options || []}
								onSelect={handleSelectOption}
								selectedIndex={currentSelection}
							/>
						) : (
							!error && (
								<p className="text-sm text-muted-foreground">
									No questions available. You can skip this step or retry fetching.
								</p>
							)
						)}
					</motion.div>
				</AnimatePresence>
			)}

			{error && questions.length === 0 ? (
				<div className="flex items-start gap-3 rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">
					<AlertCircle className="h-4 w-4 shrink-0 mt-0.5" />
					<div className="flex-1 space-y-2">
						<p>{error}</p>
						<div className="flex flex-wrap gap-2">
							<Button
								type="button"
								variant="outline"
								size="sm"
								onClick={handleManualRetry}
								disabled={isLoading || isSubmitting || isAutoRetrying}
							>
								Retry
							</Button>
							<Button type="button" variant="ghost" size="sm" onClick={onSkipAll} disabled={isSubmitting}>
								Skip all
							</Button>
						</div>
					</div>
				</div>
			) : (
				<div className="flex justify-between gap-3">
					<Button type="button" variant="outline" onClick={goToPrevious} disabled={isSubmitting}>
						Previous
					</Button>
					<div className="flex gap-2">
						<Button type="button" variant="ghost" onClick={onSkipAll} disabled={isSubmitting}>
							Skip all
						</Button>
						<Button
							type="button"
							onClick={currentSelection !== null ? goToNext : handleSkip}
							disabled={isSubmitting}
							className="min-w-[120px] bg-[var(--color-course)] text-white hover:bg-[var(--color-course)]/90"
						>
							{currentSelection !== null ? "Next" : "Skip"}
						</Button>
					</div>
				</div>
			)}
		</div>
	)
}
