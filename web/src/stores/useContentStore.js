import { create } from "zustand"
import { devtools } from "zustand/middleware"
import { toast } from "@/hooks/use-toast"
import { archiveContent, unarchiveContent } from "@/services/contentService"
import { deleteApi } from "@/services/deleteApi"

/**
 * Content Store:
 * - Actions modeled as events (what happened, not how to update)
 * - Business logic lives in store, not components
 * - All actions grouped in 'actions' object
 * - Never export store directly, only hooks
 * - Use toast function directly for notifications
 */
const contentStore = create(
	devtools(
		(set, get) => ({
			// State
			items: [],
			isLoading: false,
			error: null,

			// Actions grouped together (following docs)
			actions: {
				// Model as event: "user requested delete"
				deleteItem: async (itemId, itemType) => {
					// 1. Optimistic update (instant UI feedback)
					set((state) => ({
						items: state.items.filter((item) => item.id !== itemId && item.uuid !== itemId),
					}))

					// 2. Business logic for UI feedback
					const getTypeLabel = (type) => {
						if (type === "video") return "Video"
						if (type === "book") return "Book"
						if (type === "course" || type === "roadmap") return "Course"
						if (type === "flashcards") return "Flashcard Deck"
						return "Item"
					}
					const typeLabel = getTypeLabel(itemType)

					try {
						// 3. Persist to backend
						await deleteApi.deleteItem(itemType, itemId)

						// 4. Success notification
						toast({
							title: "Deleted",
							description: `${typeLabel} deleted successfully`,
						})

						// 5. Emit event for other components
						window.dispatchEvent(
							new CustomEvent("contentDeleted", {
								detail: { itemId, itemType },
							})
						)
					} catch (error) {
						// 6. Rollback on failure
						const currentItems = get().items
						const deletedItem = currentItems.find((item) => item.id === itemId)

						if (!deletedItem) {
							// If we can't find the item to restore, reload everything
							get().actions.reloadContent()
						}

						// 7. Error notification
						toast({
							title: "Delete Failed",
							description: error.message || "Failed to delete item. Please try again.",
							variant: "destructive",
						})
					}
				},

				// Model as event: "user requested archive"
				archiveItem: async (item) => {
					// 1. Optimistic update
					set((state) => ({
						items: state.items.map((i) => (i.id === item.id ? { ...i, archived: true } : i)),
					}))

					try {
						// 2. Persist to backend
						await archiveContent(item.type, item.id || item.uuid)

						// 3. Success notification
						toast({
							title: "Archived",
							description: `${item.title} has been archived`,
						})

						// 4. Emit event
						window.dispatchEvent(
							new CustomEvent("contentArchived", {
								detail: { itemId: item.id, itemType: item.type },
							})
						)

						// 5. Remove from visible items after animation
						setTimeout(() => {
							set((state) => ({
								items: state.items.filter((i) => i.id !== item.id),
							}))
						}, 300)
					} catch (error) {
						// 6. Rollback
						set((state) => ({
							items: state.items.map((i) => (i.id === item.id ? { ...i, archived: false } : i)),
						}))

						// 7. Error notification
						toast({
							title: "Archive Failed",
							description: error.message || "Failed to archive item",
							variant: "destructive",
						})
					}
				},

				// Model as event: "user requested unarchive"
				unarchiveItem: async (item) => {
					try {
						await unarchiveContent(item.type, item.id || item.uuid)

						toast({
							title: "Restored",
							description: `${item.title} has been restored`,
						})

						// Emit event to trigger reload
						window.dispatchEvent(
							new CustomEvent("contentUnarchived", {
								detail: { itemId: item.id, itemType: item.type },
							})
						)
					} catch (error) {
						toast({
							title: "Restore Failed",
							description: error.message || "Failed to restore item",
							variant: "destructive",
						})
					}
				},

				// Set content items
				setItems: (items) => {
					set({ items })
				},

				// Reload content (used after delete/archive failures)
				reloadContent: () => {
					// Emit event to trigger content reload
					window.dispatchEvent(new CustomEvent("reloadContent"))
				},

				// Update single item
				updateItem: (itemId, updates) => {
					set((state) => ({
						items: state.items.map((item) =>
							item.id === itemId || item.uuid === itemId ? { ...item, ...updates } : item
						),
					}))
				},

				// Remove item by ID (for external updates)
				removeItem: (itemId) => {
					set((state) => ({
						items: state.items.filter((item) => item.id !== itemId && item.uuid !== itemId),
					}))
				},
			},
		}),
		{
			name: "content-store",
		}
	)
)

// Only export custom hooks (never the store directly)
export const useContentItems = () => contentStore((state) => state.items)
export const useContentLoading = () => contentStore((state) => state.isLoading)
export const useContentError = () => contentStore((state) => state.error)
export const useContentActions = () => contentStore((state) => state.actions)

// Selector for finding specific item
export const useContentItem = (itemId) =>
	contentStore((state) => state.items.find((item) => item.id === itemId || item.uuid === itemId))
