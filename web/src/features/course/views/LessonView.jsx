import { useCallback, useEffect, useState } from "react"
import { useNavigate } from "react-router-dom"
import { LessonViewer } from "@/features/course/components/LessonViewer"
import { useCourseProgress } from "@/features/course/hooks/useCourseProgress"
import { fetchLesson } from "@/features/lesson/api/lessonApi"
import { generateCourseUrl } from "@/utils/navigationUtils"
import { useCourseService } from "../api/courseApi"

/**
 * Lesson viewer with beautiful design and MDX support
 * Fetches lesson from API and renders using the old LessonViewer component
 */
export default function LessonView({ courseId, lessonId }) {
	const [lesson, setLesson] = useState(null)
	const [loading, setLoading] = useState(true)
	const [error, setError] = useState(null)
	const navigate = useNavigate()
	const _courseService = useCourseService(courseId)
	const { updateProgressAsync, progress: courseProgress } = useCourseProgress(courseId)

	const loadLesson = useCallback(
		async ({ forceGenerate = false } = {}) => {
			if (!courseId || !lessonId) {
				return
			}

			setLoading(true)
			setError(null)

			try {
				const lessonData = await fetchLesson(courseId, lessonId, { generate: forceGenerate })
				setLesson(lessonData)
			} catch (err) {
				setError(err?.message || "Failed to load lesson")
			} finally {
				setLoading(false)
			}
		},
		[courseId, lessonId]
	)

	useEffect(() => {
		loadLesson()
	}, [loadLesson])

	const handleBack = () => {
		// Navigate back to the course overview
		const courseUrl = generateCourseUrl(courseId)
		navigate(courseUrl)
	}

	const handleMarkComplete = async (_lessonId) => {
		try {
			// Persist completion via unified progress service
			await updateProgressAsync(courseProgress?.percentage ?? 0, {
				lesson_completed: true,
				lesson_id: lessonId,
				current_lesson: String(lessonId),
			})
			// Navigate back to course outline
			const courseUrl = generateCourseUrl(courseId)
			navigate(courseUrl)
		} catch (e) {
			setError(e?.message || "Failed to mark as complete")
		}
	}

	const handleRegenerate = async (_lessonId) => {
		await loadLesson({ forceGenerate: true })
	}

	return (
		<LessonViewer
			lesson={lesson}
			isLoading={loading}
			error={error}
			onBack={handleBack}
			onMarkComplete={handleMarkComplete}
			onRegenerate={handleRegenerate}
			courseId={courseId}
			adaptiveEnabled={Boolean(
				lesson?.course?.adaptive_enabled ??
					lesson?.course?.adaptiveEnabled ??
					lesson?.adaptive_enabled ??
					lesson?.adaptiveEnabled
			)}
			isDarkMode={false}
		/>
	)
}
