import { create } from "zustand"
import { createJSONStorage, devtools, persist } from "zustand/middleware"
import { immer } from "zustand/middleware/immer"

/* eslint-disable sonarjs/todo-tag */

// Stable default objects to prevent infinite re-renders
const DEFAULT_BOOK_READING_STATE = {
	currentPage: 1,
	totalPages: 0,
	zoomLevel: 100,
	scrollPosition: { x: 0, y: 0 },
	epubState: {
		location: null,
		fontSize: 100,
		lastUpdated: null,
	},
}

const LEGACY_BOOK_STATE_KEYS = ["progress", "tocProgress", "metadata"]

/**
 * Main application store with all state slices
 * Single source of truth for client-side state
 */
const useAppStore = create(
	devtools(
		persist(
			immer((set, get) => ({
				// Authentication state (only user, no token - using httpOnly cookies)

				// Authentication actions
				// ========== BOOKS SLICE ==========
				books: {
					loading: {},
					error: {},
					readingState: {},
				},

				// ========== BOOK ACTIONS ==========
				// Set book loading state
				setBookLoading: (bookId, isLoading) => {
					set((state) => {
						state.books.loading[bookId] = isLoading
					})
				},

				// Set book error state
				setBookError: (bookId, error) => {
					set((state) => {
						state.books.error[bookId] = error
					})
				},

				// Reading state management (separate from server progress)
				updateBookReadingState: (bookId, readingState, _skipSync = false) => {
					// Ensure bookId is valid
					if (!bookId) {
						return
					}

					// Check if the state has actually changed
					const currentState = get().books.readingState[bookId]

					const hasChanged =
						!currentState ||
						(readingState.currentPage !== undefined && readingState.currentPage !== currentState.currentPage) ||
						(readingState.totalPages !== undefined && readingState.totalPages !== currentState.totalPages) ||
						(readingState.zoomMode !== undefined && readingState.zoomMode !== currentState.zoomMode) ||
						(readingState.zoomLevel !== undefined && readingState.zoomLevel !== currentState.zoomLevel) ||
						(readingState.scrollPosition !== undefined &&
							(readingState.scrollPosition.x !== currentState.scrollPosition?.x ||
								readingState.scrollPosition.y !== currentState.scrollPosition?.y))

					if (!hasChanged) {
						return // No change, don't update
					}
					set((state) => {
						// Initialize if needed
						if (!state.books.readingState[bookId]) {
							state.books.readingState[bookId] = {}
						}

						// Update the state
						state.books.readingState[bookId] = {
							...state.books.readingState[bookId],
							...readingState,
							lastUpdated: Date.now(),
						}
					})
				},

				getBookReadingState: (bookId) => {
					return get().books.readingState[bookId] || DEFAULT_BOOK_READING_STATE
				},

				setBookZoom: (bookId, zoomLevel) => {
					set((state) => {
						if (!state.books.readingState[bookId]) {
							state.books.readingState[bookId] = { ...DEFAULT_BOOK_READING_STATE }
						}
						state.books.readingState[bookId].zoomLevel = zoomLevel
						state.books.readingState[bookId].lastUpdated = Date.now()
					})
				},

				// ========== EPUB SPECIFIC ACTIONS ==========

				/**
				 * Handle EPUB location changes with business logic
				 * Updates local reading location and EPUB display progress.
				 */
				onEpubLocationChange: (bookId, location, displayPercentage) => {
					set((state) => {
						// Initialize reading state if needed
						if (!state.books.readingState[bookId]) {
							state.books.readingState[bookId] = {}
						}
						if (!state.books.readingState[bookId].epubState) {
							state.books.readingState[bookId].epubState = {}
						}

						// Update location
						state.books.readingState[bookId].epubState.location = location
						state.books.readingState[bookId].epubState.lastUpdated = Date.now()

						// Calculate and update progress if percentage is provided
						if (displayPercentage !== undefined) {
							const progressPercentage = displayPercentage === null ? 0 : Math.round(displayPercentage * 100)
							state.books.readingState[bookId].epubState.progress = progressPercentage
						}
					})
				},

				updateEpubFontSize: (bookId, fontSize) => {
					set((state) => {
						if (!state.books.readingState[bookId]) {
							state.books.readingState[bookId] = {}
						}
						if (!state.books.readingState[bookId].epubState) {
							state.books.readingState[bookId].epubState = {}
						}
						state.books.readingState[bookId].epubState.fontSize = fontSize
					})
				},

				getEpubState: (bookId) => {
					return (
						get().books.readingState[bookId]?.epubState || {
							location: null,
							fontSize: 100,
							lastUpdated: null,
						}
					)
				},

				// ========== PREFERENCES SLICE ==========
				preferences: {
					theme: "system",
					selfAssessmentEnabled: false,
					courseFocusMode: false,
					courseTimeboxMinutes: 25,
					sidebarOpen: true,
					assistantSidebarPinned: false,
					assistantModel: null,
					assistantSidebarWidth: 400,
				},

				// Preferences actions
				updatePreference: (key, value) => {
					set((state) => {
						state.preferences[key] = value
					})
				},

				setSelfAssessmentEnabled: (enabled) => {
					set((state) => {
						state.preferences.selfAssessmentEnabled = Boolean(enabled)
					})
				},

				// Assistant preference actions
				toggleAssistantSidebarPin: () => {
					const current = get().preferences.assistantSidebarPinned
					get().updatePreference("assistantSidebarPinned", !current)
				},

				setAssistantModel: (modelId) => {
					get().updatePreference("assistantModel", modelId)
				},

				setAssistantSidebarWidth: (width) => {
					const clampedWidth = Math.max(300, Math.min(800, width))
					get().updatePreference("assistantSidebarWidth", clampedWidth)
				},

				// Sidebar toggle
				toggleSidebar: () => {
					set((state) => {
						state.preferences.sidebarOpen = !state.preferences.sidebarOpen
					})
				},
			})),
			{
				name: "talimio-storage",
				storage: createJSONStorage(() => localStorage),
				partialize: (state) => ({
					books: {
						readingState: state.books.readingState,
					},
					preferences: state.preferences,
				}),
				version: 6,
				// Persisted slices only store nested subsets, so merge them explicitly and
				// keep runtime defaults like books.loading and new preference keys intact.
				merge: (persistedState, currentState) => {
					const persisted = persistedState || {}

					return {
						...currentState,
						books: {
							...currentState.books,
							readingState: persisted.books?.readingState ?? currentState.books.readingState,
						},
						preferences: {
							...currentState.preferences,
							...persisted.preferences,
						},
					}
				},
				migrate: (persistedState, version) => {
					if (!persistedState || typeof persistedState !== "object") {
						return persistedState
					}

					if (version <= 5) {
						delete persistedState.course
						delete persistedState.courses
						delete persistedState.videos
						if (persistedState.books && typeof persistedState.books === "object") {
							for (const key of LEGACY_BOOK_STATE_KEYS) {
								delete persistedState.books[key]
							}
						}
					}
					return persistedState
				},
			}
		),
		{
			name: "app-store",
		}
	)
)
// Sidebar selector
export const selectSidebarOpen = (state) => state.preferences.sidebarOpen
export const selectToggleSidebar = (state) => state.toggleSidebar

// Self-assessment selector
export const selectSelfAssessmentEnabled = (state) => state.preferences.selfAssessmentEnabled
export const selectSetSelfAssessmentEnabled = (state) => state.setSelfAssessmentEnabled

// Assistant selectors
export const selectAssistantSidebarPinned = (state) => state.preferences.assistantSidebarPinned
export const selectAssistantModel = (state) => state.preferences.assistantModel

export default useAppStore
