import { useQueryClient } from "@tanstack/react-query"
import { useNavigate } from "react-router-dom"

import { patchContentItemInCache } from "@/lib/content-query-cache"

/**
 * Content Handlers Hook:
 * - Event handlers for user interactions
 * - No business logic - just triggers events
 * - Business logic lives in stores/mutations
 * - Uses immutable patterns (no mutations)
 * - Server data handled by React Query (loadContentData)
 * - UI state updates are optimistic
 */
export function useContentHandlers({ filters, pinning, loadContentData }) {
	const navigate = useNavigate()
	const queryClient = useQueryClient()

	// Event handler: user created course
	const handleCourseCreated = async (newCourse) => {
		// Navigate to the course page immediately, then refresh content in background
		try {
			const courseId = newCourse?.id || newCourse?.course?.id || newCourse?.uuid
			if (courseId) {
				navigate(`/course/${courseId}`)
			}
		} finally {
			await loadContentData()
		}
	}

	const handleCardClick = (item) => {
		// Navigate to the appropriate page based on item type
		switch (item.type) {
			case "course": {
				// Use the new course routes for both course and course types
				navigate(`/course/${item.id}`)

				break
			}
			case "video": {
				navigate(`/videos/${item.id}`)

				break
			}
			case "book": {
				navigate(`/books/${item.id}`)

				break
			}
			// No default
		}
	}

	// Event handler: user requested delete
	const handleDeleteItem = (itemId) => {
		// Remove from pins if it was pinned
		pinning.removePinById(itemId)

		// Store handles:
		// - Optimistic update
		// - Backend call
		// - Rollback on failure
		// - Notifications
	}

	// Event handler: user requested archive
	const handleArchiveItem = async () => {
		// Store handles archiving
		// Trigger data refresh for React Query
		await loadContentData()
	}

	// Event handler: user updated tags
	const handleTagsUpdated = async (itemId, _contentType, newTags) => {
		patchContentItemInCache(queryClient, itemId, (item) => ({ ...item, tags: newTags }))

		// Refresh data via React Query
		await loadContentData()
	}

	const handleBookUploaded = (newBook) => {
		// Navigate to the book page
		navigate(`/books/${newBook.id}`)
	}

	// Event handler: user added video
	const handleVideoAdded = async (response) => {
		filters.setSearchQuery("")
		filters.setIsYoutubeMode(false)

		// Navigate to the video page
		navigate(`/videos/${response.id}`)

		// Refresh via React Query - no mutations
		await loadContentData()
	}

	return {
		handleCourseCreated,
		handleCardClick,
		handleDeleteItem,
		handleArchiveItem,
		handleTagsUpdated,
		handleBookUploaded,
		handleVideoAdded,
	}
}
