import { useNavigate } from "react-router-dom"

import { useToast } from "@/hooks/use-toast"
import { fetchContentData, processContentData } from "@/lib/api"
import { api } from "@/lib/apiClient"

export function useContentHandlers({
	filters,
	pinning,
	setContentItems,
	setFilterOptions,
	setSortOptions,
	loadContentData,
	setIsGenerating,
}) {
	const navigate = useNavigate()
	const { toast } = useToast()

	const handleGenerateCourse = async () => {
		if (!filters.searchQuery.trim()) return

		setIsGenerating(true)

		try {
			const _response = await api.post("/assistant/generate-course", {
				topic: filters.searchQuery,
				level: "beginner",
			})

			// Generate course using search query
			toast({
				title: "Generating Course",
				description: `Creating a personalized course on "${filters.searchQuery}"...`,
			})

			// Clear search after generating
			filters.setSearchQuery("")
		} catch (_error) {
			toast({
				title: "Error",
				description: "Failed to generate course. Please try again.",
				variant: "destructive",
			})
		} finally {
			setIsGenerating(false)
		}
	}

	const handleRoadmapCreated = async (_newRoadmap) => {
		try {
			// Refresh content list to include the new roadmap
			await loadContentData()
			toast({
				title: "Course Created!",
				description: "Your new course has been created successfully.",
			})
		} catch (_error) {
			toast({
				title: "Error",
				description: "Failed to refresh content.",
				variant: "destructive",
			})
		}
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

	const handleDeleteItem = (itemId, itemType) => {
		// Immediately remove the item from content state (optimistic update)
		setContentItems((prevContent) => prevContent.filter((item) => item.id !== itemId && item.uuid !== itemId))

		// Remove from pins if it was pinned
		pinning.removePinById(itemId)

		// The ContentCard component handles the actual deletion via store
		// This handler just updates local state for immediate UI feedback
	}

	const handleArchiveItem = async (_itemId, _contentType, _newArchivedState) => {
		// The ContentCard component handles the actual archiving via store
		// Just refresh the content list to update the view
		await loadContentData()
	}

	const handleTagsUpdated = async (itemId, _contentType, newTags) => {
		// Update the specific item's tags in the content list
		setContentItems((prevItems) => {
			return prevItems.map((item) => {
				if (item.id === itemId || item.uuid === itemId) {
					return {
						...item,
						tags: newTags,
					}
				}
				return item
			})
		})

		// Show success toast
		toast({
			title: "Tags Updated",
			description: "Content tags have been updated successfully.",
		})

		// Refresh filters if needed
		await loadContentData()
	}

	const handleBookUploaded = (newBook) => {
		// Navigate to the book page
		navigate(`/books/${newBook.id}`)
	}

	const handleVideoAdded = async (response) => {
		filters.setSearchQuery("")
		filters.setIsYoutubeMode(false)

		// Navigate to the video page
		navigate(`/videos/${response.id}`)

		// Refresh content list
		const data = await fetchContentData()
		const { content } = processContentData(data)
		setContentItems(
			content.map((item) => ({
				...item,
				dueDate:
					Math.random() > 0.7
						? new Date(Date.now() + (Math.random() * 7 - 2) * 24 * 60 * 60 * 1000).toISOString()
						: null,
				isPaused: Math.random() > 0.9,
				totalCards: item.cardCount,
				due: item.dueCount || Math.floor(Math.random() * 10),
				overdue: Math.random() > 0.8 ? Math.floor(Math.random() * 5) : 0,
			}))
		)
	}

	const handleDeckCreated = async () => {
		// Refresh content list
		const data = await fetchContentData()
		const { content } = processContentData(data)
		setContentItems(
			content.map((item) => ({
				...item,
				dueDate:
					Math.random() > 0.7
						? new Date(Date.now() + (Math.random() * 7 - 2) * 24 * 60 * 60 * 1000).toISOString()
						: null,
				isPaused: Math.random() > 0.9,
				totalCards: item.cardCount,
				due: item.dueCount || Math.floor(Math.random() * 10),
				overdue: Math.random() > 0.8 ? Math.floor(Math.random() * 5) : 0,
			}))
		)
		toast({
			title: "Deck Created!",
			description: "Your new flashcard deck is ready to use.",
		})
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
