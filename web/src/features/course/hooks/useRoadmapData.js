import { useEffect, useState } from "react"
import { useCourseService } from "../api/courseApi"

/**
 * Common hook for fetching course data with module progress
 * This can be used by both map and outline views
 *
 * @param {string} courseId - The ID of the course to fetch
 * @returns {Object} - Object containing course data, modules, and utility functions
 */
export function useRoadmapData(courseId) {
	const [roadmap, setRoadmap] = useState(null)
	const [modules, setModules] = useState([])
	const [isLoading, setIsLoading] = useState(false)
	const [error, setError] = useState(null)

	// Use course service for all operations
	const courseService = useCourseService(courseId)

	// Fetch course basic info
	const fetchRoadmap = useCallback(async () => {
		if (!courseId) {
			setRoadmap(null)
			return
		}
		// Use course API
		const data = await courseService.fetchCourse()
		setRoadmap(data)
	}, [courseId, courseService.fetchCourse]) // Only depend on courseId

	// Fetch modules with progress
	const fetchModules = useCallback(async () => {
		if (!courseId) {
			setModules([])
			return
		}
		// Use course API
		const moduleData = await courseService.fetchModules()
		setModules(moduleData || [])
	}, [courseId, courseService.fetchModules]) // Only depend on courseId

	// Update module status optimistically
	const updateModule = useCallback(
		async (moduleId, status) => {
			// Optimistic update
			setModules((prev) =>
				prev.map((module) =>
					module.id === moduleId
						? {
								...module,
								status,
								completionPercentage: status === "completed" ? 100 : status === "in_progress" ? 50 : 0,
							}
						: module
				)
			)

			try {
				// Use course API
				await courseService.updateModule(moduleId, { status })
				// Refetch to ensure consistency
				await fetchModules()
			} catch (err) {
				// Revert optimistic update on failure
				await fetchModules()
				throw err
			}
		},
		[fetchModules, courseService.updateModule] // Only depend on fetchModules, not courseService
	)

	// Main data fetching effect
	useEffect(() => {
		if (!courseId) {
			setRoadmap(null)
			setModules([])
			return
		}

		async function fetchData() {
			setIsLoading(true)
			setError(null)
			try {
				await Promise.all([fetchRoadmap(), fetchModules()])
			} catch (err) {
				setError(err.message || "Failed to load course data")
				setRoadmap(null)
				setModules([])
			} finally {
				setIsLoading(false)
			}
		}

		fetchData()
	}, [courseId, fetchRoadmap, fetchModules])

	// Calculate overall progress
	const overallProgress =
		modules.length > 0 ? Math.round((modules.filter((m) => m.status === "completed").length / modules.length) * 100) : 0

	return {
		roadmap,
		modules,
		isLoading,
		error,
		overallProgress,
		updateModule,
		refresh: () => {
			fetchRoadmap()
			fetchModules()
		},
	}
}
