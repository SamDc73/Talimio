import { useQuery } from "@tanstack/react-query"
import { createContext, useContext, useEffect, useMemo, useState } from "react"
import { useParams } from "react-router-dom"

import { fetchConceptFrontierByCourseId } from "@/api/courseApi"
import { useCourseData } from "@/features/course/hooks/use-course-data"
import { useOutlineData } from "@/features/course/hooks/use-outline-data"

const CourseContext = createContext(null)

export function CourseProvider({ children }) {
	const { courseId: routeCourseId } = useParams()
	const courseId = routeCourseId ?? null

	// Base course + outline data
	const { course, isLoading: courseLoading } = useCourseData(courseId)
	const { modules, isLoading: modulesLoading } = useOutlineData(courseId)

	const isAdaptiveCourse = course?.adaptive_enabled === true || course?.adaptiveEnabled === true

	// Concept frontier for adaptive progress (avgMastery)
	const [lastAdaptiveProgressPct, setLastAdaptiveProgressPct] = useState()

	const { data: frontierData } = useQuery({
		queryKey: ["course", courseId, "adaptive-concepts"],
		queryFn: ({ signal }) => fetchConceptFrontierByCourseId(courseId, signal),
		enabled: Boolean(courseId) && isAdaptiveCourse,
		staleTime: 30 * 1000,
		refetchOnWindowFocus: false,
	})

	const adaptiveProgressPct =
		typeof frontierData?.avgMastery === "number" ? Math.round(frontierData.avgMastery * 100) : undefined

	// Preserve last known adaptive progress to avoid flicker when navigating
	useEffect(() => {
		if (typeof adaptiveProgressPct === "number") {
			setLastAdaptiveProgressPct(adaptiveProgressPct)
		}
	}, [adaptiveProgressPct])

	const value = useMemo(
		() => ({
			courseId,
			courseName: course?.title || "Course",
			modules: Array.isArray(modules) ? modules : [],
			adaptiveEnabled: isAdaptiveCourse,
			adaptiveProgressPct: typeof adaptiveProgressPct === "number" ? adaptiveProgressPct : lastAdaptiveProgressPct,
			isLoading: courseLoading || modulesLoading,
		}),
		[
			courseId,
			course?.title,
			modules,
			isAdaptiveCourse,
			adaptiveProgressPct,
			lastAdaptiveProgressPct,
			courseLoading,
			modulesLoading,
		]
	)

	return <CourseContext.Provider value={value}>{children}</CourseContext.Provider>
}

// biome-ignore lint/style/useComponentExportOnlyModules: this provider and hook are intentionally co-located for course state.
export function useCourseContext() {
	const ctx = useContext(CourseContext)
	if (!ctx) {
		throw new Error("useCourseContext must be used within a CourseProvider")
	}
	return ctx
}
