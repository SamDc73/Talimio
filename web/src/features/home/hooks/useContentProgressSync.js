import { useEffect } from "react"

import useAppStore from "@/stores/useAppStore"

/**
 * Universal content progress sync hook that listens for updates from all content types
 * (courses, books, videos) and updates the homepage content items accordingly
 */
export function useContentProgressSync(setContentItems) {
	// Listen for course progress updates
	useEffect(() => {
		let refreshTimeout = null
		let updateTimeout = null

		// Handle course progress refresh
		const handleCourseProgressRefresh = async (event) => {
			if (refreshTimeout) clearTimeout(refreshTimeout)

			refreshTimeout = setTimeout(() => {
				const { courseId } = event.detail

				const store = useAppStore.getState()
				const courseProgress = store.course?.progressStats?.[courseId]
				const updatedProgress = courseProgress?.completion_percentage || 0

				setContentItems((prevItems) =>
					prevItems.map((item) =>
						item.type === "course" && item.id === courseId ? { ...item, progress: updatedProgress } : item
					)
				)
			}, 500)
		}

		// Handle course progress update
		const handleCourseProgressUpdate = (event) => {
			if (updateTimeout) clearTimeout(updateTimeout)

			updateTimeout = setTimeout(() => {
				const { courseId, progressStats } = event.detail

				setContentItems((prevItems) =>
					prevItems.map((item) =>
						item.type === "course" && item.id === courseId
							? {
									...item,
									progress: progressStats.percentage || progressStats.completion_percentage || 0,
								}
							: item
					)
				)
			}, 300)
		}

		window.addEventListener("courseProgressRefresh", handleCourseProgressRefresh)
		window.addEventListener("courseProgressUpdate", handleCourseProgressUpdate)

		return () => {
			if (refreshTimeout) clearTimeout(refreshTimeout)
			if (updateTimeout) clearTimeout(updateTimeout)
			window.removeEventListener("courseProgressRefresh", handleCourseProgressRefresh)
			window.removeEventListener("courseProgressUpdate", handleCourseProgressUpdate)
		}
	}, [setContentItems])

	// Listen for book progress updates
	useEffect(() => {
		let bookTimeout = null

		const handleBookProgressUpdate = (event) => {
			if (bookTimeout) clearTimeout(bookTimeout)

			bookTimeout = setTimeout(() => {
				const { bookId, progressStats } = event.detail
				// Fallback: optimistic update if loadContentData not provided
				setContentItems((prevItems) => {
					const updatedItems = prevItems.map((item) =>
						item.type === "book" && item.id === bookId
							? {
									...item,
									progress: progressStats.percentage || 0,
								}
							: item
					)

					return updatedItems
				})
			}, 300)
		}

		window.addEventListener("bookProgressUpdate", handleBookProgressUpdate)

		return () => {
			if (bookTimeout) clearTimeout(bookTimeout)
			window.removeEventListener("bookProgressUpdate", handleBookProgressUpdate)
		}
	}, [setContentItems]) // Remove loadContentData dependency to prevent loops

	// Listen for video progress updates
	useEffect(() => {
		let videoTimeout = null

		const handleVideoProgressUpdate = (event) => {
			if (videoTimeout) clearTimeout(videoTimeout)

			videoTimeout = setTimeout(() => {
				const { videoId, progress, progressStats } = event.detail

				// Update progress optimistically - don't reload from backend as it causes loops
				// The backend will be updated separately via the progress service
				{
					// Fallback: optimistic update if loadContentData not provided
					// Handle both old and new event formats
					const stats = progressStats || progress || {}

					// Calculate progress percentage based on different formats
					let progressPercentage = 0
					if (stats.percentage !== undefined) {
						progressPercentage = stats.percentage
					} else if (stats.duration && stats.position) {
						progressPercentage = (stats.position / stats.duration) * 100
					}

					setContentItems((prevItems) =>
						prevItems.map((item) =>
							item.type === "video" && item.id === videoId
								? {
										...item,
										progress: progressPercentage,
									}
								: item
						)
					)
				}
			}, 300)
		}

		window.addEventListener("videoProgressUpdate", handleVideoProgressUpdate)

		return () => {
			if (videoTimeout) clearTimeout(videoTimeout)
			window.removeEventListener("videoProgressUpdate", handleVideoProgressUpdate)
		}
	}, [setContentItems]) // Remove loadContentData dependency to prevent loops
}
