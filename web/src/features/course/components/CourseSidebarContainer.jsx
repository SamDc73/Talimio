import { useQuery } from "@tanstack/react-query"
import { useCourseService } from "@/api/courseApi"
import CourseSidebar from "@/components/sidebar/CourseSidebar"
import { useCourseProgress } from "@/features/course/hooks/use-course-progress"

export default function CourseSidebarContainer({
	modules = [],
	onLessonClick,
	activeLessonId = null,
	courseId,
	adaptiveEnabled = false,
	adaptiveProgressPct,
}) {
	const progressApi = useCourseProgress(courseId)
	const courseService = useCourseService(courseId)

	const { data: frontierData } = useQuery({
		queryKey: ["course", courseId, "adaptive-concepts"],
		queryFn: async () => await courseService.fetchConceptFrontier(),
		enabled: Boolean(courseId) && adaptiveEnabled,
		staleTime: 30 * 1000,
		refetchOnWindowFocus: false,
	})

	return (
		<CourseSidebar
			modules={modules}
			onLessonClick={onLessonClick}
			activeLessonId={activeLessonId}
			courseId={courseId}
			adaptiveEnabled={adaptiveEnabled}
			adaptiveProgressPct={adaptiveProgressPct}
			frontierData={frontierData}
			progressApi={progressApi}
		/>
	)
}
