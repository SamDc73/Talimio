import { useEffect, useState } from "react"
import { useNavigate } from "react-router-dom"
import { generateCourseUrl } from "@/utils/navigationUtils"
import { fetchLesson } from "../api/lessonsApi"
import { LessonViewer } from "../components/LessonViewer"

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

	useEffect(() => {
		if (!courseId || !lessonId) return

		const fetchLessonData = async () => {
			setLoading(true)
			setError(null)

			try {
				// Simple one-call API - backend handles find/generate logic
				const lessonData = await fetchLesson(courseId, lessonId)
				setLesson(lessonData)
			} catch (err) {
				setError(err.message)
			} finally {
				setLoading(false)
			}
		}

		fetchLessonData()
	}, [courseId, lessonId])

	const handleBack = () => {
		// Navigate back to the course overview
		const courseUrl = generateCourseUrl(courseId)
		navigate(courseUrl)
	}

	const handleMarkComplete = (_lessonId) => {}

	const handleRegenerate = (_lessonId) => {}

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
