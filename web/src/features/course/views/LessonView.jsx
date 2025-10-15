import { useCallback, useEffect, useState } from "react"
import { useNavigate } from "react-router-dom"
import { LessonViewer } from "@/features/course/components/LessonViewer"
import { generateCourseUrl } from "@/utils/navigationUtils"
import { fetchLesson } from "../api/lessonsApi"

const _BASE_URL = import.meta.env.VITE_API_BASE || "/api/v1"

/**
 * Lesson viewer with beautiful design and MDX support
 * Fetches lesson from API and renders using the old LessonViewer component
 */
export default function LessonView({ courseId, lessonId }) {
	const [lesson, setLesson] = useState(null)
	const [loading, setLoading] = useState(true)
	const [error, setError] = useState(null)
	const navigate = useNavigate()

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

	const handleMarkComplete = (_lessonId) => {}

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
			isDarkMode={false}
		/>
	)
}
