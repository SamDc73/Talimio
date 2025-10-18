import { useCourseProgress } from "@/features/course/hooks/useCourseProgress"
import { useCourseNavigation } from "@/utils/navigationUtils"
import OutlineNode from "../../components/navigation/OutlineNode"

/**
 * OutlineView renders the full course outline, with all modules and their lessons
 * @param {Object} props
 * @param {string} props.courseId - The ID of the course to display.
 * @param {Array} props.modules - The modules data passed from parent component.
 * @returns {JSX.Element}
 */
function OutlineView({ courseId, modules = [] }) {
	const {
		progress: courseProgress,
		toggleCompletion: toggleLessonCompletion,
		isCompleted,
	} = useCourseProgress(courseId)
	const { goToLesson } = useCourseNavigation()

	// Count total number of lessons across all modules (including nested)
	const countLessons = (items = []) => {
		let total = 0
		for (const item of items) {
			total += 1
			if (Array.isArray(item?.lessons) && item.lessons.length > 0) {
				total += countLessons(item.lessons)
			}
		}
		return total
	}

	const totalLessons = (modules || []).reduce((sum, m) => sum + countLessons(m?.lessons || []), 0)

	const handleLessonClick = async (_moduleIdx, _lessonIdx, lessonId) => {
		try {
			if (!lessonId) {
				return
			}
			goToLesson(courseId, lessonId)
		} catch (_err) {}
	}

	if (!modules || modules.length === 0) {
		return (
			<div
				className="fixed inset-0 flex flex-col items-center justify-center min-h-[calc(100vh-4rem)] text-zinc-500"
				style={{ marginLeft: 0, paddingTop: "4rem" }}
			>
				<p>No outline content available for this course.</p>
			</div>
		)
	}

	return (
		<div className="flex-1 p-4 md:p-6 lg:p-8">
			<div className="max-w-4xl mx-auto">
				{modules.map((module, idx) => (
					<OutlineNode
						key={module.id || idx}
						module={module}
						index={idx}
						onLessonClick={(lessonIdx, lessonId) => handleLessonClick(idx, lessonIdx, lessonId)}
						isLessonCompleted={isCompleted}
						toggleLessonCompletion={(lessonId) => toggleLessonCompletion(lessonId, totalLessons)}
						courseProgress={courseProgress}
					/>
				))}
			</div>
		</div>
	)
}

export default OutlineView
