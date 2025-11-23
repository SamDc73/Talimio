import { useQuery } from "@tanstack/react-query"
import { createContext, useContext, useEffect, useMemo, useState } from "react"
import { useParams } from "react-router-dom"

import { useCourseService } from "@/features/course/api/courseApi"
import { useCourseData } from "@/features/course/hooks/useCourseData"
import { useOutlineData } from "@/features/course/hooks/useOutlineData"

const CourseContext = createContext(null)

export function CourseProvider({ children }) {
	const { courseId: routeCourseId } = useParams()
	const courseId = routeCourseId ?? null

	// Base course + outline data
	const { course, isLoading: courseLoading } = useCourseData(courseId)
	const { modules, isLoading: modulesLoading } = useOutlineData(courseId)

	const isAdaptiveCourse = course?.adaptive_enabled === true || course?.adaptiveEnabled === true

	// Concept frontier for adaptive progress (avgMastery)
	const courseService = useCourseService(courseId)
	const [lastAdaptiveProgressPct, setLastAdaptiveProgressPct] = useState(undefined)

	const { data: frontierData } = useQuery({
		queryKey: ["course", courseId, "adaptive-concepts"],
		queryFn: async () => await courseService.fetchConceptFrontier(),
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

// Fast Refresh: hooks are exported from this file intentionally for DX.
// The main default export is a component (CourseProvider), so disabling this rule is safe here.
// eslint-disable-next-line react-refresh/only-export-components
export function useCourseContext() {
	const ctx = useContext(CourseContext)
	if (!ctx) {
		throw new Error("useCourseContext must be used within a CourseProvider")
	}
	return ctx
}
