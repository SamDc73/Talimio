import { useEffect, useState } from "react"
import { useCourseService } from "../api/courseApi"

/**
 * Fetches and normalizes course data for the track view.
 * @param {string} courseId - The ID of the course to fetch.
 * @returns {Object} - Object containing modules array and loading/error states
 */
export function useTrackData(courseId) {
	const [modules, setModules] = useState([])
	const [isLoading, setIsLoading] = useState(false)
	const [error, setError] = useState(null)

	// Use course service for all operations
	const courseService = useCourseService(courseId)

	useEffect(() => {
		if (!courseId) {
			setModules([])
			return
		}

		async function fetchData() {
			setIsLoading(true)
			setError(null)
			try {
				// Fetch course modules using the unified course service
				const moduleData = await courseService.fetchModules()

				if (!moduleData) {
					setModules([])
					return
				}

				// Normalize module data for track view
				// Course API returns flat modules, we need to build hierarchy
				const flatModules = Array.isArray(moduleData) ? moduleData : []

				// Find root modules (those without parent_id)
				const rootModules = flatModules.filter((module) => !module.parent_id)

				// Helper function to build module hierarchy
				const buildModuleHierarchy = (module) => {
					// Find child modules of this module
					const childModules = flatModules
						.filter((child) => child.parent_id === module.id)
						.sort((a, b) => (a.order || 0) - (b.order || 0))

					return {
						id: module.id,
						title: module.title || "Untitled",
						description: module.description || "",
						order: module.order || 0,
						status: module.status || "not_started",
						// Include children for track view
						children: childModules.map((child) => buildModuleHierarchy(child)),
					}
				}

				// Process and sort root modules
				const normalizedModules = rootModules
					.map((module) => buildModuleHierarchy(module))
					.sort((a, b) => (a.order || 0) - (b.order || 0))

				setModules(normalizedModules)
			} catch (err) {
				setError(err.message || "Failed to load course data")
				setModules([])
			} finally {
				setIsLoading(false)
			}
		}

		fetchData()
	}, [courseId, courseService.fetchModules]) // Only depend on courseId, not the service functions

	return { modules, isLoading, error }
}
