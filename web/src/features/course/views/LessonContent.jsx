import { useCallback, useEffect, useMemo, useRef, useState } from "react"
import { useParams, useSearchParams } from "react-router-dom"
import { ConfirmationDialog } from "@/components/ConfirmationDialog"
import { useCourseContext } from "@/features/course/CourseContext"
import { LessonViewer } from "@/features/course/components/LessonViewer"
import { RegenerateModal } from "@/features/course/components/RegenerateModal"
import { useCourseProgress } from "@/features/course/hooks/use-course-progress"
import { useLessonActions } from "@/features/course/hooks/use-lesson-actions"
import { useLessonData } from "@/features/course/hooks/use-lesson-data"

export default function LessonContent() {
	const { lessonId } = useParams()
	const { courseId, modules, adaptiveEnabled } = useCourseContext()
	const [searchParams, setSearchParams] = useSearchParams()
	const [isRegenerateOpen, setIsRegenerateOpen] = useState(false)
	const [isNextPassConfirmOpen, setIsNextPassConfirmOpen] = useState(false)
	const [pendingRegenerateLessonId, setPendingRegenerateLessonId] = useState(null)
	const [regenerateStatus, setRegenerateStatus] = useState(null)
	const [nextPassStatus, setNextPassStatus] = useState(null)
	const [currentWindowIndex, setCurrentWindowIndex] = useState(0)
	const autoStartedNextPassRef = useRef(new Set())
	const selectedVersionId = searchParams.get("versionId")?.trim() || null
	const adaptiveFlow = searchParams.get("adaptiveFlow") === "true"

	const {
		data: lesson,
		isLoading,
		error,
	} = useLessonData(courseId, lessonId, {
		versionId: selectedVersionId,
		adaptiveFlow,
	})
	const { progress, rawMetadata, updateProgressAsync } = useCourseProgress(courseId)

	const {
		handleBack,
		handleLessonNavigation,
		handleMarkComplete,
		handleRegenerate,
		handleStartNextPass,
		isRegeneratingLesson,
		isStartingNextPass,
	} = useLessonActions(courseId)

	const errorMessage = error?.message || (typeof error === "string" ? error : null)
	const lessonWindows = Array.isArray(lesson?.windows) ? lesson.windows : []
	const savedWindowIndex = useMemo(() => {
		const positions = rawMetadata?.lesson_window_positions
		if (!positions || typeof positions !== "object") {
			return 0
		}

		const rawIndex = positions[lessonId]
		if (!Number.isInteger(rawIndex)) {
			return 0
		}

		return rawIndex
	}, [lessonId, rawMetadata])

	useEffect(() => {
		if (lessonWindows.length === 0) {
			setCurrentWindowIndex(0)
			return
		}

		const nextIndex = Math.min(Math.max(savedWindowIndex, 0), lessonWindows.length - 1)
		setCurrentWindowIndex((value) => (value === nextIndex ? value : nextIndex))
	}, [lessonWindows.length, savedWindowIndex])

	const handleRegenerateOpen = useCallback((id) => {
		setPendingRegenerateLessonId(id)
		setRegenerateStatus(null)
		setIsRegenerateOpen(true)
	}, [])

	const handleRegenerateSubmit = useCallback(
		async ({ critiqueText, applyAcrossCourse }) => {
			if (!pendingRegenerateLessonId) {
				return
			}

			try {
				await handleRegenerate(pendingRegenerateLessonId, critiqueText, applyAcrossCourse)
				setIsRegenerateOpen(false)
				setPendingRegenerateLessonId(null)
				setRegenerateStatus(null)
			} catch (submissionError) {
				setRegenerateStatus({
					type: "error",
					message: submissionError?.message || "We couldn't regenerate this lesson right now.",
				})
			}
		},
		[handleRegenerate, pendingRegenerateLessonId]
	)

	const handleRegenerateOpenChange = useCallback((nextOpen) => {
		setIsRegenerateOpen(nextOpen)
		if (!nextOpen) {
			setPendingRegenerateLessonId(null)
		}
	}, [])

	const clearLessonSelectionParams = useCallback(
		({ clearAdaptiveFlow = false } = {}) => {
			setSearchParams((currentParams) => {
				const nextParams = new URLSearchParams(currentParams)
				nextParams.delete("versionId")
				if (clearAdaptiveFlow) {
					nextParams.delete("adaptiveFlow")
				}
				return nextParams
			})
		},
		[setSearchParams]
	)

	const startNextPass = useCallback(
		async ({ force = false, clearAdaptiveFlow = false } = {}) => {
			if (!lesson?.id) {
				return null
			}

			setNextPassStatus({
				type: "inProgress",
				message: force
					? `Starting v${lesson?.nextPass?.majorVersion || "2"}.0 now.`
					: `Opening v${lesson?.nextPass?.majorVersion || "2"}.0.`,
			})

			try {
				const nextPassLesson = await handleStartNextPass(lesson.id, { force })
				clearLessonSelectionParams({ clearAdaptiveFlow })
				setNextPassStatus(null)
				return nextPassLesson
			} catch (submissionError) {
				setNextPassStatus({
					type: "error",
					message: submissionError?.message || "We couldn't start the deeper version right now.",
				})
				throw submissionError
			}
		},
		[clearLessonSelectionParams, handleStartNextPass, lesson]
	)

	const handleStartNextPassAction = useCallback(() => {
		if (!lesson?.nextPass) {
			return
		}

		setNextPassStatus(null)
		if (lesson.nextPass.status === "available_early") {
			setIsNextPassConfirmOpen(true)
			return
		}

		void startNextPass({ force: false, clearAdaptiveFlow: adaptiveFlow })
	}, [adaptiveFlow, lesson?.nextPass, startNextPass])

	const handleConfirmNextPass = useCallback(() => {
		void startNextPass({ force: true, clearAdaptiveFlow: adaptiveFlow })
	}, [adaptiveFlow, startNextPass])

	const handleVersionSelect = useCallback(
		(versionId) => {
			setSearchParams((currentParams) => {
				const nextParams = new URLSearchParams(currentParams)
				if (!versionId || String(versionId) === String(lesson?.currentVersionId)) {
					nextParams.delete("versionId")
				} else {
					nextParams.set("versionId", String(versionId))
				}
				return nextParams
			})
		},
		[lesson?.currentVersionId, setSearchParams]
	)

	useEffect(() => {
		if (!adaptiveFlow || selectedVersionId || !lesson?.id || !lesson?.nextPass || isStartingNextPass) {
			return
		}

		if (lesson.nextPass.status !== "recommended_now") {
			return
		}

		if (!lesson.versionId || !lesson.currentVersionId || String(lesson.versionId) !== String(lesson.currentVersionId)) {
			return
		}

		const autoStartKey = `${lesson.id}:${lesson.versionId}:${lesson.nextPass.majorVersion}`
		if (autoStartedNextPassRef.current.has(autoStartKey)) {
			return
		}

		autoStartedNextPassRef.current.add(autoStartKey)
		void startNextPass({ force: false, clearAdaptiveFlow: true })
	}, [adaptiveFlow, isStartingNextPass, lesson, selectedVersionId, startNextPass])

	const persistWindowIndex = useCallback(
		async (nextIndex) => {
			if (!courseId || !lesson?.id) {
				return
			}

			const currentPositions =
				rawMetadata?.lesson_window_positions && typeof rawMetadata.lesson_window_positions === "object"
					? rawMetadata.lesson_window_positions
					: {}

			if (currentPositions[lesson.id] === nextIndex) {
				return
			}

			await updateProgressAsync(progress?.percentage ?? 0, {
				lesson_window_positions: {
					...currentPositions,
					[lesson.id]: nextIndex,
				},
				current_lesson_id: String(lesson.id),
			})
		},
		[courseId, lesson?.id, progress?.percentage, rawMetadata, updateProgressAsync]
	)

	const handleWindowChange = useCallback(
		(nextIndex) => {
			if (!Number.isInteger(nextIndex) || nextIndex < 0 || nextIndex >= lessonWindows.length) {
				return
			}

			setCurrentWindowIndex((value) => (value === nextIndex ? value : nextIndex))
			void persistWindowIndex(nextIndex)
		},
		[lessonWindows.length, persistWindowIndex]
	)

	return (
		<>
			<LessonViewer
				lesson={lesson}
				isLoading={isLoading}
				error={errorMessage}
				onBack={handleBack}
				onMarkComplete={(id) => handleMarkComplete(id)}
				onRegenerate={handleRegenerateOpen}
				isRegeneratingLesson={isRegeneratingLesson}
				regenerateStatus={regenerateStatus}
				modules={modules}
				onLessonNavigate={(id) => handleLessonNavigation(id)}
				onStartNextPass={handleStartNextPassAction}
				adaptiveEnabled={adaptiveEnabled}
				courseId={courseId}
				onVersionSelect={handleVersionSelect}
				activeWindowIndex={currentWindowIndex}
				isStartingNextPass={isStartingNextPass}
				nextPassStatus={nextPassStatus}
				onWindowChange={handleWindowChange}
			/>
			<ConfirmationDialog
				open={isNextPassConfirmOpen}
				onOpenChange={setIsNextPassConfirmOpen}
				title={`v${lesson?.nextPass?.majorVersion || "2"}.0 is usually better later`}
				description="If you have an exam or want to double down on this topic right now, you can still start it early."
				confirmText={`Start v${lesson?.nextPass?.majorVersion || "2"}.0 anyway`}
				cancelText="Stay on current version"
				onConfirm={handleConfirmNextPass}
				isDestructive={false}
			/>
			<RegenerateModal
				open={isRegenerateOpen}
				onOpenChange={handleRegenerateOpenChange}
				onRegenerate={handleRegenerateSubmit}
				isRegenerating={isRegeneratingLesson}
			/>
		</>
	)
}
