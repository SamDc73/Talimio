import { useQuery } from "@tanstack/react-query"
import { Loader2 } from "lucide-react"
import { useCallback, useEffect, useMemo, useRef, useState } from "react"
import { Link, useSearchParams } from "react-router-dom"
import { useCourseService } from "@/api/courseApi"
import { Button } from "@/components/Button"
import { LatexExpression } from "@/components/quiz/LatexExpression"
import { useCourseContext } from "@/features/course/CourseContext"
import { useLatexPracticeReview } from "@/features/course/hooks/use-latex-practice-review"
import logger from "@/lib/logger"

const MICRO_BATCH_SIZE = 4
const PREFETCH_THRESHOLD = 2

function normalizeConcept(item) {
	if (!item || typeof item !== "object") {
		return null
	}

	const conceptId = item.id ?? item.conceptId ?? item.concept_id ?? null
	if (!conceptId) {
		return null
	}

	const lessonId = item.lessonId ?? item.lesson_id ?? item.lessonIdRef ?? item.lesson_id_ref ?? item.lesson?.id ?? null

	if (!lessonId) {
		return null
	}

	return {
		conceptId: String(conceptId),
		lessonId: String(lessonId),
		title: item.name || item.title || "Concept",
	}
}

function normalizeDrill(rawItem, fallbackConceptId, fallbackLessonId) {
	if (!rawItem || typeof rawItem !== "object") {
		return null
	}

	const question = typeof rawItem.question === "string" ? rawItem.question.trim() : ""
	const expectedLatex = typeof rawItem.expectedLatex === "string" ? rawItem.expectedLatex.trim() : ""
	if (!question || !expectedLatex) {
		return null
	}

	const conceptId = rawItem.conceptId ? String(rawItem.conceptId) : fallbackConceptId
	const lessonId = rawItem.lessonId ? String(rawItem.lessonId) : fallbackLessonId
	if (!conceptId || !lessonId) {
		return null
	}

	const structureSignature =
		typeof rawItem.structureSignature === "string" && rawItem.structureSignature.trim().length > 0
			? rawItem.structureSignature.trim()
			: "question.unknown"

	const predictedPCorrect =
		typeof rawItem.predictedPCorrect === "number" && !Number.isNaN(rawItem.predictedPCorrect)
			? Math.max(0, Math.min(1, rawItem.predictedPCorrect))
			: 0.5

	const coreModel =
		typeof rawItem.coreModel === "string" && rawItem.coreModel.trim().length > 0 ? rawItem.coreModel : "unknown-model"

	return {
		conceptId,
		lessonId,
		question,
		expectedLatex,
		hints: Array.isArray(rawItem.hints) ? rawItem.hints.filter(Boolean).map(String) : [],
		structureSignature,
		predictedPCorrect,
		coreModel,
	}
}

function drillKey(item) {
	if (!item) {
		return ""
	}
	const normalizedQuestion = item.question.trim().toLowerCase().replace(/\s+/g, " ").replace(/\d+/g, "n")
	return `${item.conceptId}:${item.structureSignature}:${normalizedQuestion}`
}

export default function PracticeView() {
	const { courseId, adaptiveEnabled } = useCourseContext()
	const courseService = useCourseService(courseId)
	const [searchParams] = useSearchParams()
	const focusConceptIdParam = searchParams.get("focusConceptId")?.trim() || null

	const [scheduledIndex, setScheduledIndex] = useState(0)
	const [queue, setQueue] = useState([])
	const [isGenerating, setIsGenerating] = useState(false)
	const [generationError, setGenerationError] = useState(null)
	const [noMoreItems, setNoMoreItems] = useState(false)
	const [completedCount, setCompletedCount] = useState(0)

	const seenDrillKeysRef = useRef(new Set())
	const generatingRef = useRef(false)
	const noMoreItemsRef = useRef(false)

	const { data: frontierData, isLoading: frontierLoading } = useQuery({
		queryKey: ["course", courseId, "adaptive-concepts"],
		queryFn: async () => await courseService.fetchConceptFrontier(),
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

	const mode = focusConceptIdParam ? "focused" : "scheduled"
	const sessionScopeKey = mode === "focused" ? focusConceptIdParam : "scheduled"
	const scheduledComplete = mode === "scheduled" && scheduledIndex >= dueConcepts.length
	const activeConcept = mode === "focused" ? focusConcept : (dueConcepts[scheduledIndex] ?? null)
	const activeConceptKey = activeConcept ? `${activeConcept.conceptId}:${activeConcept.lessonId}` : ""
	const currentQuestion = queue[0] ?? null

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
		async (requestedCount = MICRO_BATCH_SIZE) => {
			if (!courseId || !activeConcept?.conceptId || !activeConcept?.lessonId) {
				return
			}
			if (generatingRef.current || noMoreItemsRef.current) {
				return
			}

			generatingRef.current = true
			setIsGenerating(true)
			setGenerationError(null)

			try {
				const response = await courseService.fetchPracticeDrills({
					conceptId: activeConcept.conceptId,
					count: requestedCount,
				})
				const drills = Array.isArray(response?.drills) ? response.drills : []
				if (drills.length === 0) {
					noMoreItemsRef.current = true
					setNoMoreItems(true)
					return
				}

				setQueue((previousQueue) => {
					const nextQueue = [...previousQueue]
					for (const rawItem of drills) {
						const normalized = normalizeDrill(rawItem, activeConcept.conceptId, activeConcept.lessonId)
						if (!normalized) {
							continue
						}
						const key = drillKey(normalized)
						if (!key || seenDrillKeysRef.current.has(key)) {
							continue
						}
						seenDrillKeysRef.current.add(key)
						nextQueue.push(normalized)
					}
					return nextQueue
				})
			} catch (error) {
				const message = error?.message || "Failed to generate practice drills"
				setGenerationError(message)
				logger.error("Failed to fetch practice drills", error, {
					courseId,
					conceptId: activeConcept.conceptId,
				})
			} finally {
				generatingRef.current = false
				setIsGenerating(false)
			}
		},
		[activeConcept?.conceptId, activeConcept?.lessonId, courseId, courseService]
	)

	useEffect(() => {
		if (!sessionScopeKey) {
			return
		}
		setCompletedCount(0)
		setScheduledIndex(0)
	}, [sessionScopeKey])

	useEffect(() => {
		if (!activeConceptKey && mode !== "scheduled") {
			return
		}
		setQueue([])
		setGenerationError(null)
		setNoMoreItems(false)
		noMoreItemsRef.current = false
		seenDrillKeysRef.current = new Set()
	}, [activeConceptKey, mode])

	useEffect(() => {
		if (!activeConcept?.conceptId || !activeConcept?.lessonId) {
			return
		}
		const threshold = mode === "scheduled" ? 0 : PREFETCH_THRESHOLD
		const batchSize = mode === "scheduled" ? 1 : MICRO_BATCH_SIZE
		if (queue.length > threshold) {
			return
		}
		if (noMoreItemsRef.current) {
			return
		}
		void requestMore(batchSize)
	}, [activeConcept?.conceptId, activeConcept?.lessonId, mode, queue.length, requestMore])

	useEffect(() => {
		if (mode !== "scheduled" || scheduledComplete) {
			return
		}
		if (!noMoreItems || isGenerating || queue.length > 0) {
			return
		}
		setScheduledIndex((value) => value + 1)
	}, [isGenerating, mode, noMoreItems, queue.length, scheduledComplete])

	const handleItemComplete = useCallback(() => {
		setCompletedCount((value) => value + 1)
		setQueue((previousQueue) => previousQueue.slice(1))
		if (mode === "scheduled") {
			setScheduledIndex((value) => value + 1)
		}
	}, [mode])

	const handleGrade = useCallback(
		async (payload) => {
			if (!currentQuestion) {
				throw new Error("No active question available")
			}

			const reviewMetadata = {
				question: currentQuestion.question,
				structureSignature: currentQuestion.structureSignature,
				predictedPCorrect: currentQuestion.predictedPCorrect,
				coreModel: currentQuestion.coreModel,
			}

			return await submitAnswer({
				...payload,
				conceptId: currentQuestion.conceptId,
				practiceContext: "drill",
				reviewMetadata,
			})
		},
		[currentQuestion, submitAnswer]
	)

	const handleSkip = useCallback(
		async (payload) => {
			if (!currentQuestion) {
				throw new Error("No active question available")
			}

			const reviewMetadata = {
				question: currentQuestion.question,
				structureSignature: currentQuestion.structureSignature,
				predictedPCorrect: currentQuestion.predictedPCorrect,
				coreModel: currentQuestion.coreModel,
			}

			return await submitSkip({
				...payload,
				conceptId: currentQuestion.conceptId,
				practiceContext: "drill",
				reviewMetadata,
			})
		},
		[currentQuestion, submitSkip]
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
		return (
			<div className="w-full max-w-3xl mx-auto py-12 px-6">
				<div className="rounded-xl border border-border bg-card p-6 space-y-3">
					<h1 className="text-2xl font-semibold text-foreground">Practice</h1>
					<p className="text-muted-foreground">All caught up. No concepts are due for review.</p>
				</div>
			</div>
		)
	}

	if (scheduledComplete) {
		return (
			<div className="w-full max-w-3xl mx-auto py-12 px-6">
				<div className="rounded-xl border border-border bg-card p-6 space-y-3">
					<h1 className="text-2xl font-semibold text-foreground">Practice</h1>
					<p className="text-muted-foreground">All caught up. You completed today&apos;s due concepts.</p>
					<p className="text-sm text-muted-foreground">Questions answered this session: {completedCount}</p>
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
				key={`${currentQuestion.conceptId}-${currentQuestion.structureSignature}`}
				question={currentQuestion.question}
				expectedLatex={currentQuestion.expectedLatex}
				hints={currentQuestion.hints}
				practiceContext="drill"
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
					<p className="text-xs uppercase tracking-[0.2em] text-muted-foreground">Practice Bowl</p>
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
