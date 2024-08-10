import { useQueryClient } from "@tanstack/react-query"
import { createContext, useContext, useEffect } from "react"

export const ProgressContext = createContext()

/**
 * Provider for unified progress state management
 * Listens for progress updates from any source and syncs with React Query cache
 */
export function ProgressProvider({ children }) {
	const queryClient = useQueryClient()

	// Listen for progress updates from any source
	useEffect(() => {
		const handleProgressUpdate = (event) => {
			const { contentId, progress } = event.detail

			// Update React Query cache for all queries containing this contentId
			queryClient.setQueriesData({ queryKey: ["progress"], exact: false }, (old) => {
				if (!old || typeof old !== "object") return old
				return {
					...old,
					[contentId]: progress,
				}
			})
		}

		// Listen for legacy events from content types
		const handleBookProgressUpdate = (event) => {
			const { bookId, progressStats } = event.detail
			handleProgressUpdate({
				detail: {
					contentId: bookId,
					progress: progressStats?.percentage || 0,
				},
			})
		}

		const handleVideoProgressUpdate = (event) => {
			const { videoId, progress, progressStats } = event.detail
			const stats = progressStats || progress || {}

			let progressPercentage = 0
			if (stats.percentage !== undefined) {
				progressPercentage = stats.percentage
			} else if (stats.duration && stats.position) {
				progressPercentage = (stats.position / stats.duration) * 100
			}

			handleProgressUpdate({
				detail: {
					contentId: videoId,
					progress: progressPercentage,
				},
			})
		}

		const handleCourseProgressUpdate = (event) => {
			const { courseId, progressStats } = event.detail
			handleProgressUpdate({
				detail: {
					contentId: courseId,
					progress: progressStats?.percentage || progressStats?.completion_percentage || 0,
				},
			})
		}

		// Add event listeners
		window.addEventListener("progressUpdated", handleProgressUpdate)
		window.addEventListener("bookProgressUpdate", handleBookProgressUpdate)
		window.addEventListener("videoProgressUpdate", handleVideoProgressUpdate)
		window.addEventListener("courseProgressUpdate", handleCourseProgressUpdate)

		// Cleanup
		return () => {
			window.removeEventListener("progressUpdated", handleProgressUpdate)
			window.removeEventListener("bookProgressUpdate", handleBookProgressUpdate)
			window.removeEventListener("videoProgressUpdate", handleVideoProgressUpdate)
			window.removeEventListener("courseProgressUpdate", handleCourseProgressUpdate)
		}
	}, [queryClient])

	return <ProgressContext value={{}}>{children}</ProgressContext>
}

export function useProgressContext() {
	const context = useContext(ProgressContext)
	if (context === undefined) {
		throw new Error("useProgressContext must be used within a ProgressProvider")
	}
	return context
}
