import { useNavigate } from "react-router-dom"
import { api } from "@/lib/apiClient"

/**
 * Content Handlers Hook:
 * - Event handlers for user interactions
 * - No business logic - just triggers events
 * - Business logic lives in stores/mutations
 * - Uses immutable patterns (no mutations)
 * - Server data handled by React Query (loadContentData)
 * - UI state updates are optimistic
 */
export function useContentHandlers({ filters, pinning, setContentItems, loadContentData, setIsGenerating }) {
	const navigate = useNavigate()

	const handleGenerateCourse = async () => {
		if (!filters.searchQuery.trim()) return

		setIsGenerating(true)

		try {
			const _response = await api.post("/assistant/generate-course", {
				topic: filters.searchQuery,
				level: "beginner",
			})

			// Clear search after generating
			filters.setSearchQuery("")
		} catch (_error) {
		} finally {
			setIsGenerating(false)
		}
	}

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
		if (item.type === "course") {
			// Use the new course routes for both course and course types
			navigate(`/course/${item.id}`)
		} else if (item.type === "video") {
			navigate(`/videos/${item.id}`)
		} else if (item.type === "book") {
			navigate(`/books/${item.id}`)
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
		// Optimistic update using immutable pattern
		setContentItems((prevItems) =>
			prevItems.map((item) => (item.id === itemId || item.uuid === itemId ? { ...item, tags: newTags } : item))
		)

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
		handleGenerateCourse,
		handleCourseCreated,
		handleCardClick,
		handleDeleteItem,
		handleArchiveItem,
		handleTagsUpdated,
		handleBookUploaded,
		handleVideoAdded,
	}
}
