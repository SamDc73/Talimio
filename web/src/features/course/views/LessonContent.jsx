import { useCallback, useState } from "react"
import { useParams } from "react-router-dom"
import { useCourseContext } from "@/features/course/CourseContext"
import { LessonViewer } from "@/features/course/components/LessonViewer"
import { RegenerateModal } from "@/features/course/components/RegenerateModal"
import { useLessonActions } from "@/features/course/hooks/use-lesson-actions"
import { useLessonData } from "@/features/course/hooks/use-lesson-data"

export default function LessonContent() {
	const { lessonId } = useParams()
	const { courseId, modules, adaptiveEnabled } = useCourseContext()
	const [isRegenerateOpen, setIsRegenerateOpen] = useState(false)
	const [pendingRegenerateLessonId, setPendingRegenerateLessonId] = useState(null)
	const [regenerateStatus, setRegenerateStatus] = useState(null)

	const { data: lesson, isLoading, error } = useLessonData(courseId, lessonId)

	const { handleBack, handleLessonNavigation, handleMarkComplete, handleRegenerate, isRegeneratingLesson } =
		useLessonActions(courseId)

	const errorMessage = error?.message || (typeof error === "string" ? error : null)

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
