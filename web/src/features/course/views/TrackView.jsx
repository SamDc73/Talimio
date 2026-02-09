import { useQuery } from "@tanstack/react-query"
import { Loader2 } from "lucide-react"
import { useMemo } from "react"
import { useCourseService } from "@/api/courseApi"
import { useCourseContext } from "@/features/course/CourseContext"
import TrackPath from "@/features/course/components/TrackPath"

export default function TrackView() {
	const { courseId, modules, adaptiveEnabled } = useCourseContext()

	const courseService = useCourseService(courseId)

	const { data, isLoading } = useQuery({
		queryKey: ["course", courseId, "adaptive-concepts"],
		queryFn: async () => await courseService.fetchConceptFrontier(),
		enabled: Boolean(courseId) && adaptiveEnabled,
		staleTime: 30 * 1000,
		refetchOnWindowFocus: false,
	})

	// Compute the set of currently available lessons (due + frontier) for locking logic.
	const availableLessonIds = useMemo(() => {
		if (!adaptiveEnabled || !data) return
		const toId = (c) => c?.lessonId ?? c?.lesson_id ?? c?.lessonIdRef ?? c?.lesson_id_ref ?? c?.lesson?.id ?? c?.id
		const ids = new Set()
		for (const c of data?.dueForReview || []) {
			const id = toId(c)
			if (id !== undefined && id !== null) ids.add(String(id))
		}
		for (const c of data?.frontier || []) {
			const id = toId(c)
			if (id !== undefined && id !== null) ids.add(String(id))
		}
		return [...ids]
	}, [adaptiveEnabled, data])

	const fallbackModules = useMemo(() => {
		if (!adaptiveEnabled || !data) return []
		const toLesson = (concept, order) => {
			const lessonId =
				concept?.lessonId ?? concept?.lesson_id ?? concept?.lessonIdRef ?? concept?.lesson_id_ref ?? concept?.lesson?.id
			if (!lessonId) return null
			return { id: lessonId, order, title: concept?.name || "Lesson", description: concept?.description || "" }
		}
		const seq = [
			...(Array.isArray(data?.dueForReview) ? data.dueForReview : []),
			...(Array.isArray(data?.frontier) ? data.frontier : []),
			...(Array.isArray(data?.comingSoon) ? data.comingSoon : []),
		]
		const lessons = seq.map((c, i) => toLesson(c, i + 1)).filter(Boolean)
		if (lessons.length === 0) return []
		const chunkSize = 4
		const groups = []
		for (let i = 0; i < lessons.length; i += chunkSize) {
			const groupIndex = Math.floor(i / chunkSize) + 1
			const slice = lessons.slice(i, i + chunkSize).map((l, idx) => ({ ...l, order: idx + 1 }))
			groups.push({
				id: `adaptive-${groupIndex}`,
				title: "",
				description: "",
				lessons: slice,
			})
		}
		if (groups.length === 1 && lessons.length > 1) {
			const only = groups[0]
			const mid = Math.ceil(only.lessons.length / 2)
			return [
				{
					...only,
					id: "adaptive-1",
					title: "",
					lessons: only.lessons.slice(0, mid).map((l, idx) => ({ ...l, order: idx + 1 })),
				},
				{
					...only,
					id: "adaptive-2",
					title: "",
					lessons: only.lessons.slice(mid).map((l, idx) => ({ ...l, order: idx + 1 })),
				},
			]
		}
		return groups
	}, [adaptiveEnabled, data])

	if (adaptiveEnabled && isLoading) {
		return (
			<div className="flex min-h-[calc(100vh-4rem)] items-center justify-center">
				<Loader2 className="size-8  animate-spin text-primary" />
			</div>
		)
	}

	const effectiveModules = Array.isArray(modules) && modules.length > 0 ? modules : fallbackModules
	return <TrackPath courseId={courseId} modules={effectiveModules} availableLessonIds={availableLessonIds} />
}
