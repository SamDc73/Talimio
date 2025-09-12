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

			// Generate course using search query
			console.log("Action completed")

			// Clear search after generating
			filters.setSearchQuery("")
		} catch (_error) {
			console.log("Error")
		} finally {
			setIsGenerating(false)
		}
	}

	// Event handler: user created roadmap
	const handleRoadmapCreated = async (_newRoadmap) => {
		// Just trigger data refresh - let React Query handle the fetching
		await loadContentData()
		// Toast moved to store action or mutation onSuccess
	}

	const handleCardClick = (item) => {
		// Navigate to the appropriate page based on item type
		if (item.type === "course" || item.type === "roadmap") {
			// Use the new course routes for both course and roadmap types
			navigate(`/course/${item.id}`)
		} else if (item.type === "video") {
			navigate(`/videos/${item.id}`)
		} else if (item.type === "book") {
			navigate(`/books/${item.id}`)
		} else if (item.type === "flashcards") {
			navigate(`/flashcards/${item.id}`)
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

	// Event handler: user created deck
	const handleDeckCreated = async () => {
		// Refresh via React Query
		await loadContentData()
		// Toast should be in mutation onSuccess
		console.log("Deck Created!")
	}

	return {
		handleGenerateCourse,
		handleRoadmapCreated,
		handleCardClick,
		handleDeleteItem,
		handleArchiveItem,
		handleTagsUpdated,
		handleBookUploaded,
		handleVideoAdded,
		handleDeckCreated,
	}
}
