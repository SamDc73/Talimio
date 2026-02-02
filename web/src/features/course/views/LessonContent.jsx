import { useParams } from "react-router-dom"
import { useCourseContext } from "@/features/course/CourseContext.jsx"
import { LessonViewer } from "@/features/course/components/LessonViewer"
import { useLessonActions } from "@/features/course/hooks/useLessonActions"
import { useLessonData } from "@/features/course/hooks/useLessonData"

export default function LessonContent() {
	const { lessonId } = useParams()
	const { courseId, modules, adaptiveEnabled } = useCourseContext()

	const { data: lesson, isLoading, error } = useLessonData(courseId, lessonId)

	const { handleBack, handleLessonNavigation, handleMarkComplete, handleRegenerate } = useLessonActions(courseId)

	const errorMessage = error?.message || (typeof error === "string" ? error : null)

	return (
		<LessonViewer
			lesson={lesson}
			isLoading={isLoading}
			error={errorMessage}
			onBack={handleBack}
			onMarkComplete={(id) => handleMarkComplete(id)}
			onRegenerate={(id) => handleRegenerate(id)}
			modules={modules}
			onLessonNavigate={(id) => handleLessonNavigation(id)}
			adaptiveEnabled={adaptiveEnabled}
			courseId={courseId}
		/>
	)
}
