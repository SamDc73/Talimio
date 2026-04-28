import { useQuery } from "@tanstack/react-query"
import { Loader2, X } from "lucide-react"
import { useCallback, useEffect, useMemo, useRef, useState } from "react"
import { Link, useNavigate, useSearchParams } from "react-router-dom"
import { fetchConceptFrontierByCourseId, useCourseService } from "@/api/courseApi"
import { Button } from "@/components/Button"
import { LatexExpression } from "@/components/quiz/LatexExpression"
import { useCourseContext } from "@/features/course/CourseContext"
import { useLatexPracticeReview } from "@/features/course/hooks/use-latex-practice-review"
import logger from "@/lib/logger"
import { cn } from "@/lib/utils"

const MICRO_BATCH_SIZE = 4
const PREFETCH_THRESHOLD = 2
const SOFT_STOP_RECENT_WINDOW = 5
const SOFT_STOP_MIN_ANSWERS = 10
const SOFT_STOP_LOW_ACCURACY_THRESHOLD = 0.4
const SOFT_STOP_CEILING_QUESTIONS = 30
const SOFT_STOP_CEILING_MS = 30 * 60 * 1000
const SOFT_STOP_MAX_EVENTS = 50
const PRACTICE_ATTENTION_NOTICE_CLASS_NAME = "rounded-lg border border-due-today/30 bg-due-today/10 p-4"
const PRACTICE_ATTENTION_DISMISS_CLASS_NAME = "text-due-today-text hover:bg-due-today/15 hover:text-due-today-text"

function normalizeConcept(item) {
	if (!item || typeof item !== "object") {
		return null
	}

	const conceptId = item.id ?? item.conceptId ?? null
	if (!conceptId) {
		return null
	}

	const lessonId = item.lessonId ?? item.lesson?.id ?? null

	if (!lessonId) {
		return null
	}

	const masteryCandidate = item.mastery ?? item.confidence ?? item.strength ?? null
	const masteryValue = typeof masteryCandidate === "string" ? Number(masteryCandidate) : masteryCandidate
	const mastery = typeof masteryValue === "number" && Number.isFinite(masteryValue) ? masteryValue : null

	return {
		conceptId: String(conceptId),
		lessonId: String(lessonId),
		title: item.name || item.title || "Concept",
		mastery,
	}
}

function normalizeDrill(rawItem) {
	if (!rawItem || typeof rawItem !== "object") {
		return null
	}

	const question = typeof rawItem.question === "string" ? rawItem.question.trim() : ""
	const questionId = rawItem.questionId ? String(rawItem.questionId) : ""
	let inputKind = ""
	if (rawItem.inputKind === "text") {
		inputKind = "text"
	} else if (rawItem.inputKind === "math_latex") {
		inputKind = "math_latex"
	}
	const conceptId = rawItem.conceptId ? String(rawItem.conceptId) : ""
	const lessonId = rawItem.lessonId ? String(rawItem.lessonId) : ""
	if (!question || !questionId || !inputKind || !conceptId || !lessonId) {
		return null
	}

	return {
		questionId,
		conceptId,
		lessonId,
		question,
		inputKind,
		hints: rawItem.hints,
	}
}

function drillKey(item) {
	if (!item) {
		return ""
	}
	return item.questionId
}

export default function PracticeView() {
	const { courseId, adaptiveEnabled } = useCourseContext()
	const courseService = useCourseService(courseId)
	const [searchParams] = useSearchParams()
	const navigate = useNavigate()
	const focusConceptIdParam = searchParams.get("focusConceptId")?.trim() || null

	const [scheduledIndex, setScheduledIndex] = useState(0)
	const fetchIndexRef = useRef(0)
	const [queue, setQueue] = useState([])
	const [isGenerating, setIsGenerating] = useState(false)
	const [generationError, setGenerationError] = useState(null)
	const [noMoreItems, setNoMoreItems] = useState(false)
	const [completedCount, setCompletedCount] = useState(0)
	const [softStopNudge, setSoftStopNudge] = useState(null)
	const [incorrectStreak, setIncorrectStreak] = useState({ conceptId: null, count: 0 })
	const [escapeHatchDismissedFor, setEscapeHatchDismissedFor] = useState(null)

	const answerEventsRef = useRef([])
	const sessionStartedAtRef = useRef(Date.now())
	const sessionStartAccuracyRef = useRef(null)
	const completedQuestionsRef = useRef(0)
	const nudgeShownRef = useRef({ performance: false, ceiling: false })
	const seenDrillKeysRef = useRef(new Set())

	const generatingRef = useRef(false)

	const { data: frontierData, isLoading: frontierLoading } = useQuery({
		queryKey: ["course", courseId, "adaptive-concepts"],
		queryFn: ({ signal }) => fetchConceptFrontierByCourseId(courseId, signal),
		enabled: Boolean(courseId) && adaptiveEnabled,
		staleTime: 30 * 1000,
		refetchOnWindowFocus: false,
	})

	const dueConcepts = useMemo(() => {
		if (!frontierData?.dueForReview || !Array.isArray(frontierData.dueForReview)) {
			return []
		}
		return frontierData.dueForReview.map((item) => normalizeConcept(item)).filter(Boolean)
	}, [frontierData])

	const mode = focusConceptIdParam ? "focused" : "scheduled"
	const practiceSessionKey = `${mode}:${focusConceptIdParam ?? ""}`
	const scheduledComplete = mode === "scheduled" && scheduledIndex >= dueConcepts.length
	const bonusPracticeSuggestions = useMemo(() => {
		const candidates = []
		if (Array.isArray(frontierData?.frontier)) candidates.push(...frontierData.frontier)
		if (Array.isArray(frontierData?.dueForReview)) candidates.push(...frontierData.dueForReview)
		const normalized = candidates.map((item) => normalizeConcept(item)).filter(Boolean)
		const unique = new Map()
		for (const concept of normalized) {
			if (!unique.has(concept.conceptId)) {
				if (mode === "scheduled" && scheduledComplete && dueConcepts.some((d) => d.conceptId === concept.conceptId)) {
					continue
				}
				unique.set(concept.conceptId, concept)
			}
		}
		const sorted = [...unique.values()].toSorted((a, b) => (a.mastery ?? 1) - (b.mastery ?? 1))
		return sorted.slice(0, 5)
	}, [frontierData, mode, scheduledComplete, dueConcepts])

	const allAdaptiveConcepts = useMemo(() => {
		const buckets = []
		if (Array.isArray(frontierData?.dueForReview)) buckets.push(...frontierData.dueForReview)
		if (Array.isArray(frontierData?.frontier)) buckets.push(...frontierData.frontier)
		if (Array.isArray(frontierData?.comingSoon)) buckets.push(...frontierData.comingSoon)
		return buckets.map((item) => normalizeConcept(item)).filter(Boolean)
	}, [frontierData])

	const focusConcept = useMemo(() => {
		if (!focusConceptIdParam) {
			return null
		}
		return allAdaptiveConcepts.find((item) => item.conceptId === focusConceptIdParam) ?? null
	}, [allAdaptiveConcepts, focusConceptIdParam])

	const activeConcept = mode === "focused" ? focusConcept : (dueConcepts[scheduledIndex] ?? null)
	const currentQuestion = queue[0] ?? null

	const showLessonEscapeHatch =
		Boolean(courseId && activeConcept?.lessonId && activeConcept?.conceptId) &&
		incorrectStreak.conceptId === activeConcept.conceptId &&
		incorrectStreak.count >= 3 &&
		escapeHatchDismissedFor !== activeConcept.conceptId

	const handleDismissLessonEscapeHatch = useCallback(() => {
		if (activeConcept?.conceptId) {
			setEscapeHatchDismissedFor(activeConcept.conceptId)
		}
	}, [activeConcept?.conceptId])

	const {
		submitAnswer,
		submitSkip,
		isSubmitting,
		error: submissionError,
	} = useLatexPracticeReview({
		courseId,
		lessonId: currentQuestion?.lessonId ?? null,
		conceptId: currentQuestion?.conceptId ?? null,
		practiceContext: "drill",
	})

	const requestMore = useCallback(
		async (conceptToFetch, requestedCount = MICRO_BATCH_SIZE) => {
			if (!courseId || !conceptToFetch?.conceptId || !conceptToFetch?.lessonId) {
				return
			}
			if (generatingRef.current) {
				return
			}

			generatingRef.current = true
			setIsGenerating(true)
			setGenerationError(null)
			setNoMoreItems(false)

			try {
				const response = await courseService.fetchQuestionSet({
					conceptId: conceptToFetch.conceptId,
					count: requestedCount,
					lessonId: conceptToFetch.lessonId,
					practiceContext: "drill",
				})
				if (!response || !Array.isArray(response.questions)) {
					setNoMoreItems(true)
					setGenerationError("Invalid practice question response payload.")
					logger.error("Invalid practice question response payload", {
						courseId,
						conceptId: conceptToFetch.conceptId,
						response,
					})
					return
				}

				const drills = response.questions
				if (drills.length === 0) {
					setNoMoreItems(true)
					return
				}

				const acceptedDrills = []
				const batchKeys = new Set()
				let rejectedInvalidCount = 0
				let rejectedDuplicateCount = 0
				for (const rawItem of drills) {
					const normalized = normalizeDrill(rawItem)
					if (!normalized) {
						rejectedInvalidCount += 1
						continue
					}
					const key = drillKey(normalized)
					if (!key || batchKeys.has(key) || seenDrillKeysRef.current.has(key)) {
						rejectedDuplicateCount += 1
						continue
					}
					batchKeys.add(key)
					seenDrillKeysRef.current.add(key)
					acceptedDrills.push(normalized)
				}

				if (acceptedDrills.length === 0) {
					setNoMoreItems(true)
					setGenerationError("No usable questions were returned for this concept right now.")
					logger.error("Practice drill batch returned no usable questions", {
						courseId,
						conceptId: conceptToFetch.conceptId,
						receivedCount: drills.length,
						rejectedInvalidCount,
						rejectedDuplicateCount,
					})
					return
				}

				setQueue((previousQueue) => [...previousQueue, ...acceptedDrills])
			} catch (error) {
				const message = error?.message || "Failed to generate practice questions"
				setGenerationError(message)
				logger.error("Failed to fetch practice questions", error, {
					courseId,
					conceptId: conceptToFetch.conceptId,
				})
			} finally {
				generatingRef.current = false
				setIsGenerating(false)
			}
		},
		[courseId, courseService]
	)

	const maybeTriggerCeilingNudge = useCallback(
		(nowMs) => {
			if (!courseId || nudgeShownRef.current.ceiling) {
				return
			}

			const elapsedMs = Math.max(0, nowMs - sessionStartedAtRef.current)
			if (completedQuestionsRef.current < SOFT_STOP_CEILING_QUESTIONS && elapsedMs < SOFT_STOP_CEILING_MS) {
				return
			}

			setSoftStopNudge((previous) => {
				if (previous) {
					return previous
				}
				nudgeShownRef.current.ceiling = true
				return {
					kind: "ceiling",
					message: "Great session! Take a break or keep going?",
					stopTo: `/course/${courseId}`,
				}
			})
		},
		[courseId]
	)

	const recordAnswerEvent = useCallback(
		({ isCorrect, conceptId }) => {
			if (typeof isCorrect !== "boolean") {
				return
			}

			const normalizedConceptId = conceptId ? String(conceptId) : null
			if (normalizedConceptId) {
				setIncorrectStreak((previous) => {
					if (isCorrect) {
						return { conceptId: normalizedConceptId, count: 0 }
					}
					if (previous.conceptId === normalizedConceptId) {
						return { conceptId: normalizedConceptId, count: previous.count + 1 }
					}
					return { conceptId: normalizedConceptId, count: 1 }
				})

				if (isCorrect) {
					setEscapeHatchDismissedFor((previous) => (previous === normalizedConceptId ? null : previous))
				}
			}

			const nowMs = Date.now()
			const events = answerEventsRef.current
			events.push(isCorrect)
			if (events.length > SOFT_STOP_MAX_EVENTS) {
				events.shift()
			}

			if (sessionStartAccuracyRef.current === null && events.length >= SOFT_STOP_RECENT_WINDOW) {
				const startWindow = events.slice(0, SOFT_STOP_RECENT_WINDOW)
				const startCorrect = startWindow.filter(Boolean).length
				sessionStartAccuracyRef.current = startCorrect / SOFT_STOP_RECENT_WINDOW
			}

			const startAccuracy = sessionStartAccuracyRef.current
			if (
				!nudgeShownRef.current.performance &&
				events.length >= SOFT_STOP_MIN_ANSWERS &&
				events.length >= SOFT_STOP_RECENT_WINDOW * 2 &&
				typeof startAccuracy === "number" &&
				!Number.isNaN(startAccuracy)
			) {
				const recentWindow = events.slice(-SOFT_STOP_RECENT_WINDOW)
				const recentCorrect = recentWindow.filter(Boolean).length
				const recentAccuracy = recentCorrect / SOFT_STOP_RECENT_WINDOW

				if (recentAccuracy < SOFT_STOP_LOW_ACCURACY_THRESHOLD && recentAccuracy < startAccuracy) {
					const stopTo = activeConcept?.lessonId
						? `/course/${courseId}/lesson/${activeConcept.lessonId}?adaptiveFlow=true`
						: `/course/${courseId}`
					setSoftStopNudge((previous) => {
						if (previous) {
							return previous
						}
						nudgeShownRef.current.performance = true
						return {
							kind: "performance",
							message: "You might benefit from reviewing the lesson. Keep practicing or open lesson?",
							stopTo,
						}
					})
				}
			}

			maybeTriggerCeilingNudge(nowMs)
		},
		[activeConcept?.lessonId, courseId, maybeTriggerCeilingNudge]
	)

	const handleSoftStop = useCallback(() => {
		const destination = softStopNudge?.stopTo
		setSoftStopNudge(null)
		if (destination) {
			navigate(destination)
		}
	}, [navigate, softStopNudge])

	const handleKeepPracticing = useCallback(() => {
		setSoftStopNudge(null)
	}, [])

	useEffect(() => {
		if (!courseId) {
			return
		}
		setCompletedCount(0)
		completedQuestionsRef.current = 0
		setScheduledIndex(0)
		fetchIndexRef.current = 0
		answerEventsRef.current = []
		sessionStartAccuracyRef.current = null
		sessionStartedAtRef.current = Date.now()
		nudgeShownRef.current = { performance: false, ceiling: false }
		setSoftStopNudge(null)
		setIncorrectStreak({ conceptId: null, count: 0 })
		setEscapeHatchDismissedFor(null)
		seenDrillKeysRef.current.clear()
	}, [courseId])

	useEffect(() => {
		if (!courseId || nudgeShownRef.current.ceiling) {
			return
		}

		const timer = setInterval(() => {
			maybeTriggerCeilingNudge(Date.now())
		}, 15_000)

		return () => {
			clearInterval(timer)
		}
	}, [courseId, maybeTriggerCeilingNudge])

	useEffect(() => {
		setQueue([])
		setGenerationError(null)
		setNoMoreItems(false)
		setCompletedCount(0)
		completedQuestionsRef.current = 0
		answerEventsRef.current = []
		sessionStartAccuracyRef.current = null
		sessionStartedAtRef.current = Date.now()
		nudgeShownRef.current = { performance: false, ceiling: false }
		setSoftStopNudge(null)
		setIncorrectStreak({ conceptId: null, count: 0 })
		setEscapeHatchDismissedFor(null)
		seenDrillKeysRef.current.clear()
		if (practiceSessionKey.startsWith("scheduled:")) {
			setScheduledIndex(0)
			fetchIndexRef.current = 0
		}
	}, [practiceSessionKey])

	useEffect(() => {
		if (generatingRef.current || generationError || noMoreItems) {
			return
		}
		const threshold = PREFETCH_THRESHOLD
		const batchSize = mode === "scheduled" ? 1 : MICRO_BATCH_SIZE
		if (queue.length > threshold) {
			return
		}

		if (mode === "focused") {
			if (!focusConcept) return
			void requestMore(focusConcept, batchSize)
		} else if (mode === "scheduled") {
			const conceptToFetch = dueConcepts[fetchIndexRef.current]
			if (conceptToFetch) {
				fetchIndexRef.current += 1
				void requestMore(conceptToFetch, batchSize)
			}
		}
	}, [generationError, mode, noMoreItems, queue.length, requestMore, focusConcept, dueConcepts])

	useEffect(() => {
		if (mode !== "scheduled" || scheduledComplete) {
			return
		}
		if (!noMoreItems || isGenerating || queue.length > 0) {
			return
		}
		setNoMoreItems(false)
		setScheduledIndex((value) => value + 1)
	}, [isGenerating, mode, noMoreItems, queue.length, scheduledComplete])

	const handleItemComplete = useCallback(() => {
		completedQuestionsRef.current += 1
		setCompletedCount((value) => value + 1)
		maybeTriggerCeilingNudge(Date.now())
		setQueue((previousQueue) => previousQueue.slice(1))
		if (mode === "scheduled") {
			setScheduledIndex((value) => value + 1)
		}
	}, [maybeTriggerCeilingNudge, mode])

	const handleGrade = useCallback(
		async (payload) => {
			if (!currentQuestion) {
				throw new Error("No active question available")
			}

			const result = await submitAnswer({
				...payload,
				questionId: currentQuestion.questionId,
				conceptId: currentQuestion.conceptId,
				practiceContext: "drill",
			})
			recordAnswerEvent({ isCorrect: Boolean(result?.grade?.isCorrect), conceptId: currentQuestion.conceptId })
			return result
		},
		[currentQuestion, recordAnswerEvent, submitAnswer]
	)

	const handleSkip = useCallback(
		async (payload) => {
			if (!currentQuestion) {
				throw new Error("No active question available")
			}

			const result = await submitSkip({
				...payload,
				questionId: currentQuestion.questionId,
				conceptId: currentQuestion.conceptId,
				practiceContext: "drill",
			})
			recordAnswerEvent({ isCorrect: false, conceptId: currentQuestion.conceptId })
			return result
		},
		[currentQuestion, recordAnswerEvent, submitSkip]
	)

	if (!adaptiveEnabled) {
		return (
			<div className="w-full max-w-3xl mx-auto py-12 px-6">
				<div className="rounded-xl border border-border bg-card p-6 space-y-3">
					<h1 className="text-2xl font-semibold text-foreground">Practice</h1>
					<p className="text-muted-foreground">Practice bowl is available only for adaptive courses.</p>
				</div>
			</div>
		)
	}

	if (frontierLoading) {
		return (
			<div className="flex min-h-[calc(100vh-4rem)] items-center justify-center w-full">
				<Loader2 className="size-8 animate-spin text-primary" />
			</div>
		)
	}

	if (mode === "focused" && focusConceptIdParam && !focusConcept) {
		return (
			<div className="w-full max-w-3xl mx-auto py-12 px-6">
				<div className="rounded-xl border border-border bg-card p-6 space-y-3">
					<h1 className="text-2xl font-semibold text-foreground">Practice</h1>
					<p className="text-muted-foreground">The requested concept is not available in this course right now.</p>
					<Link to={`/course/${courseId}/practice`} className="inline-flex">
						<Button size="sm">Open scheduled practice</Button>
					</Link>
				</div>
			</div>
		)
	}

	if (mode === "scheduled" && dueConcepts.length === 0) {
		const hasSuggestions = bonusPracticeSuggestions.length > 0
		return (
			<div className="w-full max-w-3xl mx-auto py-12 px-6">
				<div className="rounded-xl border border-border bg-card p-6 space-y-3">
					<h1 className="text-2xl font-semibold text-foreground">Practice</h1>
					<p className="text-muted-foreground">You&apos;re caught up.</p>
					{hasSuggestions ? (
						<div className="pt-2 space-y-3">
							<div className="text-sm font-medium text-foreground">Bonus practice</div>
							<div className="flex flex-wrap gap-2">
								{bonusPracticeSuggestions.map((concept) => (
									<Button key={concept.conceptId} asChild variant="outline" size="sm">
										<Link to={`/course/${courseId}/practice?focusConceptId=${encodeURIComponent(concept.conceptId)}`}>
											{concept.title}
										</Link>
									</Button>
								))}
							</div>
						</div>
					) : null}
				</div>
			</div>
		)
	}

	if (scheduledComplete) {
		const hasSuggestions = bonusPracticeSuggestions.length > 0
		return (
			<div className="w-full max-w-3xl mx-auto py-12 px-6">
				<div className="rounded-xl border border-border bg-card p-6 space-y-3">
					<h1 className="text-2xl font-semibold text-foreground">Practice</h1>
					<p className="text-muted-foreground">You&apos;re caught up.</p>
					<p className="text-sm text-muted-foreground">Questions answered this session: {completedCount}</p>
					{hasSuggestions ? (
						<div className="pt-2 space-y-3">
							<div className="text-sm font-medium text-foreground">Bonus practice</div>
							<div className="flex flex-wrap gap-2">
								{bonusPracticeSuggestions.map((concept) => (
									<Button key={concept.conceptId} asChild variant="outline" size="sm">
										<Link to={`/course/${courseId}/practice?focusConceptId=${encodeURIComponent(concept.conceptId)}`}>
											{concept.title}
										</Link>
									</Button>
								))}
							</div>
						</div>
					) : null}
				</div>
			</div>
		)
	}

	let questionPanel = (
		<div className="rounded-lg border border-border bg-muted/30 p-4 text-sm text-muted-foreground">
			Preparing your next drill...
		</div>
	)

	if (currentQuestion) {
		questionPanel = (
			<LatexExpression
				key={drillKey(currentQuestion)}
				question={currentQuestion.question}
				answerKind={currentQuestion.inputKind}
				hints={currentQuestion.hints}
				practiceContext="drill"
				completeOnAnyGrade
				onGrade={handleGrade}
				onSkip={handleSkip}
				onComplete={handleItemComplete}
			/>
		)
	} else if (isGenerating) {
		questionPanel = (
			<div className="flex items-center gap-2 text-sm text-muted-foreground">
				<Loader2 className="size-4 animate-spin" />
				Loading next question...
			</div>
		)
	} else if (noMoreItems) {
		questionPanel = (
			<div className="rounded-lg border border-border bg-muted/30 p-4 text-sm text-muted-foreground">
				No more questions right now.
			</div>
		)
	}

	return (
		<div className="w-full max-w-4xl mx-auto py-8 px-4 md:px-6">
			<div className="rounded-xl border border-border bg-card shadow-sm p-6 space-y-6">
				<div className="space-y-2">
					<p className="text-xs uppercase tracking-[0.2em] text-muted-foreground">Adaptive Practice</p>
					<h1 className="text-2xl font-semibold text-foreground">{activeConcept?.title || "Practice"}</h1>
					<p className="text-sm text-muted-foreground">
						{mode === "focused"
							? "Focused mode"
							: `Scheduled mode · ${Math.min(scheduledIndex + 1, dueConcepts.length)}/${dueConcepts.length}`}
					</p>
				</div>

				{generationError ? (
					<div className="rounded-lg border border-destructive/40 bg-destructive/10 p-4 text-sm text-destructive">
						{generationError}
					</div>
				) : null}

				{submissionError ? (
					<div className="rounded-lg border border-destructive/40 bg-destructive/10 p-4 text-sm text-destructive">
						{submissionError.message || "Failed to submit answer"}
					</div>
				) : null}

				{showLessonEscapeHatch ? (
					<div
						className={cn(PRACTICE_ATTENTION_NOTICE_CLASS_NAME, "flex flex-wrap items-center justify-between gap-3")}
					>
						<Button asChild size="sm" variant="outline">
							<Link to={`/course/${courseId}/lesson/${encodeURIComponent(activeConcept.lessonId)}?adaptiveFlow=true`}>
								Open lesson for {activeConcept.title}
							</Link>
						</Button>
						<Button
							variant="ghost"
							size="icon"
							onClick={handleDismissLessonEscapeHatch}
							className={PRACTICE_ATTENTION_DISMISS_CLASS_NAME}
							aria-label="Dismiss lesson suggestion"
						>
							<X className="size-4" />
						</Button>
					</div>
				) : null}

				{softStopNudge ? (
					<div className={cn(PRACTICE_ATTENTION_NOTICE_CLASS_NAME, "space-y-3")}>
						<p className="text-sm font-medium text-foreground">{softStopNudge.message}</p>
						<div className="flex flex-col sm:flex-row gap-2">
							<Button size="sm" onClick={handleSoftStop} className="sm:w-auto">
								{softStopNudge.kind === "performance" ? "Open lesson" : "Stop"}
							</Button>
							<Button variant="outline" size="sm" onClick={handleKeepPracticing} className="sm:w-auto">
								Keep practicing
							</Button>
						</div>
					</div>
				) : null}

				{questionPanel}

				<div className="flex items-center justify-between text-xs text-muted-foreground">
					<span>Queue: {queue.length}</span>
					<span>Completed this session: {completedCount}</span>
				</div>

				{isSubmitting ? <p className="text-xs text-muted-foreground">Submitting review...</p> : null}
			</div>
		</div>
	)
}
