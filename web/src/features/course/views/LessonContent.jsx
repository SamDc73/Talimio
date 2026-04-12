import { useCallback, useEffect, useMemo, useState } from "react"
import { useParams, useSearchParams } from "react-router-dom"
import { useCourseContext } from "@/features/course/CourseContext"
import { LessonViewer } from "@/features/course/components/LessonViewer"
import { useCourseProgress } from "@/features/course/hooks/use-course-progress"
import { RegenerateModal } from "@/features/course/components/RegenerateModal"
import { useLessonActions } from "@/features/course/hooks/use-lesson-actions"
import { useLessonData } from "@/features/course/hooks/use-lesson-data"

export default function LessonContent() {
	const { lessonId } = useParams()
	const { courseId, modules, adaptiveEnabled } = useCourseContext()
	const [searchParams, setSearchParams] = useSearchParams()
	const [isRegenerateOpen, setIsRegenerateOpen] = useState(false)
	const [pendingRegenerateLessonId, setPendingRegenerateLessonId] = useState(null)
	const [regenerateStatus, setRegenerateStatus] = useState(null)
	const [currentWindowIndex, setCurrentWindowIndex] = useState(0)
	const selectedVersionId = searchParams.get("versionId")?.trim() || null

	const { data: lesson, isLoading, error } = useLessonData(courseId, lessonId, selectedVersionId)
	const { progress, rawMetadata, updateProgressAsync } = useCourseProgress(courseId)

	const { handleBack, handleLessonNavigation, handleMarkComplete, handleRegenerate, isRegeneratingLesson } =
		useLessonActions(courseId)

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
		async (critiqueText) => {
			if (!pendingRegenerateLessonId) {
				return
			}

			try {
				await handleRegenerate(pendingRegenerateLessonId, critiqueText)
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
				adaptiveEnabled={adaptiveEnabled}
				courseId={courseId}
				onVersionSelect={handleVersionSelect}
				activeWindowIndex={currentWindowIndex}
				onWindowChange={handleWindowChange}
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
