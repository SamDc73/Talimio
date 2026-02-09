// Loads and normalizes the course data for Outline mode

import { useEffect, useState } from "react"
import { api } from "@/lib/apiClient"

/**
 * Fetches and normalizes course data for the outline view.
 * @param {string} courseId - The ID of the course to fetch.
 * @returns {Object} - Object containing modules array and loading/error states
 */
export function useOutlineData(courseId) {
	const [modules, setModules] = useState([])
	const [isLoading, setIsLoading] = useState(false)
	const [error, setError] = useState(null)

	useEffect(() => {
		if (!courseId) {
			setModules([])
			return
		}

		async function fetchData() {
			setIsLoading(true)
			setError(null)
			try {
				const courseData = await api.get(`/courses/${courseId}`)
				setModules(courseData.modules || [])
			} catch (err) {
				setError(err.message || "Failed to load course data")
				setModules([])
			} finally {
				setIsLoading(false)
			}
		}

		fetchData()
	}, [courseId])

	return { modules, isLoading, error }
}
