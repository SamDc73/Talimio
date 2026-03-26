import { create } from "zustand"
import { createJSONStorage, devtools, persist } from "zustand/middleware"
import { immer } from "zustand/middleware/immer"

/* eslint-disable sonarjs/todo-tag */

// Stable default objects to prevent infinite re-renders
const DEFAULT_BOOK_PROGRESS = {
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

const dispatchProgressUpdated = (contentId, progressValue, metadata = {}) => {
	if (typeof window === "undefined" || !contentId) {
		return
	}

	window.dispatchEvent(
		new CustomEvent("progressUpdated", {
			detail: {
				contentId,
				progress: progressValue,
				metadata,
			},
		})
	)
}

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
					// Book progress: bookId -> { percentage, totalItems, completedItems, items, lastUpdated }
					progress: {},
					// Loading states: bookId -> boolean
					loading: {},
					// Error states: bookId -> Error | null
					error: {},
					// Book metadata cache
					metadata: {},
					// Book reading state: bookId -> { currentPage, totalPages, zoomLevel, scrollPosition, epubState }
					readingState: {},
				},

				// ========== BOOK ACTIONS ==========
				// Standardized actions matching course/video patterns

				// Set book progress
				setBookProgress: (bookId, progress) => {
					const nextProgress = {
						...progress,
						lastUpdated: Date.now(),
					}

					set((state) => {
						state.books.progress[bookId] = nextProgress
					})

					const metadata = {
						content_type: "book",
						toc_progress: nextProgress.items || {},
						total_chapters: nextProgress.totalItems ?? Object.keys(nextProgress.items || {}).length,
						completed_chapters_count: nextProgress.completedItems ?? 0,
					}

					if (nextProgress.currentPage !== undefined) {
						metadata.current_page = nextProgress.currentPage
					}
					if (nextProgress.totalPages !== undefined) {
						metadata.total_pages = nextProgress.totalPages
					}
					if (nextProgress.zoomLevel !== undefined) {
						metadata.zoom_level = nextProgress.zoomLevel
					}

					dispatchProgressUpdated(bookId, nextProgress.percentage ?? 0, metadata)
				},

				// Toggle book item completion (chapters)
				toggleBookItem: (bookId, chapterId) => {
					const progress = get().books.progress[bookId] || {
						percentage: 0,
						totalItems: 0,
						completedItems: 0,
						items: {},
					}

					const wasCompleted = progress.items[chapterId] || false
					const isCompleted = !wasCompleted

					// Calculate new progress
					const completedItems = progress.completedItems + (isCompleted ? 1 : -1)
					const percentage = progress.totalItems > 0 ? Math.round((completedItems / progress.totalItems) * 100) : 0

					const newProgress = {
						...progress,
						items: {
							...progress.items,
							[chapterId]: isCompleted,
						},
						completedItems,
						percentage,
						lastUpdated: Date.now(),
						// clientId: getClientId(), // Track which client made the change - TODO: implement getClientId
					}

					// Track this as a local update to prevent echo

					// Update optimistically
					set((state) => {
						state.books.progress[bookId] = newProgress
					})

					// Dispatch unified progress event for dashboard sync
					const metadata = {
						content_type: "book",
						toc_progress: newProgress.items || {},
						total_chapters: newProgress.totalItems ?? Object.keys(newProgress.items || {}).length,
						completed_chapters_count: newProgress.completedItems ?? 0,
					}

					dispatchProgressUpdated(bookId, newProgress.percentage ?? 0, metadata)
				},

				// Batch update book items
				batchUpdateBook: (bookId, updates) => {
					const progress = get().books.progress[bookId] || {
						percentage: 0,
						totalItems: 0,
						completedItems: 0,
						items: {},
					}

					// Apply all updates
					const newItems = { ...progress.items }
					for (const { itemId, completed } of updates) {
						newItems[itemId] = completed
					}

					// Calculate new progress
					const completedItems = Object.values(newItems).filter(Boolean).length
					const percentage = progress.totalItems > 0 ? Math.round((completedItems / progress.totalItems) * 100) : 0

					const newProgress = {
						...progress,
						items: newItems,
						completedItems,
						percentage,
						lastUpdated: Date.now(),
						// clientId: getClientId(), // Track which client made the change - TODO: implement getClientId
					}

					// Track this as a local update to prevent echo

					// Update state
					set((state) => {
						state.books.progress[bookId] = newProgress
					})

					// Dispatch unified progress event
					const metadata = {
						content_type: "book",
						toc_progress: newProgress.items || {},
						total_chapters: newProgress.totalItems ?? Object.keys(newProgress.items || {}).length,
						completed_chapters_count: newProgress.completedItems ?? 0,
					}

					dispatchProgressUpdated(bookId, newProgress.percentage ?? 0, metadata)
				},

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

				// Get book progress
				getBookProgress: (bookId) => {
					return get().books.progress[bookId] || null
				},

				// Reading state management (separate from progress)
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
					return get().books.readingState[bookId] || DEFAULT_BOOK_PROGRESS
				},

				setBookZoom: (bookId, zoomLevel) => {
					set((state) => {
						if (!state.books.readingState[bookId]) {
							state.books.readingState[bookId] = { ...DEFAULT_BOOK_PROGRESS }
						}
						state.books.readingState[bookId].zoomLevel = zoomLevel
						state.books.readingState[bookId].lastUpdated = Date.now()
					})
				},

				// ========== EPUB SPECIFIC ACTIONS ==========

				/**
				 * Calculate EPUB progress percentage from rendition data
				 * @param {number|undefined} displayPercentage - The percentage from react-reader (0-1)
				 * @returns {number} Progress percentage (0-100)
				 */
				calculateEpubProgress: (displayPercentage) => {
					if (displayPercentage === undefined || displayPercentage === null) {
						return 0
					}
					// displayPercentage comes as a decimal (0-1), convert to percentage (0-100)
					return Math.round(displayPercentage * 100)
				},

				/**
				 * Handle EPUB location changes with business logic
				 * Updates location, calculates progress, and syncs to API
				 */
				onEpubLocationChange: (bookId, location, displayPercentage) => {
					const { calculateEpubProgress } = get()

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
							const progressPercentage = calculateEpubProgress(displayPercentage)
							state.books.readingState[bookId].epubState.progress = progressPercentage

							// Update overall book progress
							if (!state.books.progress[bookId]) {
								state.books.progress[bookId] = { percentage: 0 }
							}
							state.books.progress[bookId].percentage = progressPercentage
							state.books.progress[bookId].lastUpdated = Date.now()
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

				// Initialize book progress from book data
				initializeBookProgress: (bookId, book) => {
					if (!book?.tableOfContents) {
						return
					}

					// Store book metadata for progress calculations
					set((state) => {
						state.books.metadata[bookId] = {
							...book,
							tableOfContents: book.tableOfContents,
						}
					})

					// Count only leaf chapters (not parent chapters)
					const getAllLeafChapters = (chapters, seenIds = new Set()) => {
						const leafChapters = []
						for (const chapter of chapters) {
							if (!seenIds.has(chapter.id)) {
								seenIds.add(chapter.id)
								if (chapter.children && chapter.children.length > 0) {
									// Parent chapter - recurse into children
									const childChapters = getAllLeafChapters(chapter.children, seenIds)
									leafChapters.push(...childChapters)
								} else {
									// Leaf chapter - add to list
									leafChapters.push(chapter)
								}
							}
						}
						return leafChapters
					}

					const leafChapters = getAllLeafChapters(
						Array.isArray(book.tableOfContents) ? book.tableOfContents : [book.tableOfContents]
					)

					// Initialize standardized progress from server data if available
					const items = {}
					if (book.progress?.tocProgress) {
						for (const [chapterId, completed] of Object.entries(book.progress.tocProgress)) {
							items[chapterId] = completed
						}
					}

					// Count only completed leaf chapters
					const completedLeafIds = new Set()
					for (const leafChapter of leafChapters) {
						if (items[leafChapter.id]) {
							completedLeafIds.add(leafChapter.id)
						}
					}

					const completedItems = completedLeafIds.size
					const totalItems = leafChapters.length
					const percentage = totalItems > 0 ? Math.round((completedItems / totalItems) * 100) : 0

					const progress = {
						percentage,
						totalItems,
						completedItems,
						items,
						lastUpdated: Date.now(),
					}

					// Set standardized progress
					set((state) => {
						state.books.progress[bookId] = progress
					})
				},

				// ========== VIDEOS SLICE ==========
				videos: {
					progress: {},
					playbackState: {},
				},

				// ========== VIDEO ACTIONS ==========

				// Get video progress
				getVideoProgress: (videoId) => {
					return (
						get().videos.progress[videoId] || {
							percentage: 0,
							totalItems: 0,
							completedItems: 0,
							items: {},
							lastUpdated: null,
						}
					)
				},

				// Video progress update (used by VideoViewer)
				updateVideoProgress: (videoId, progressData) => {
					const position = progressData.position ?? progressData.lastPosition ?? 0
					const percentage = progressData.percentage || 0

					set((state) => {
						state.videos.playbackState[videoId] = {
							...state.videos.playbackState[videoId],
							currentTime: position,
							lastUpdated: Date.now(),
						}
					})

					const storedVideoProgress = get().videos.progress[videoId] || {}
					const duration = progressData.duration ?? storedVideoProgress.duration ?? 0

					const metadata = {
						content_type: "video",
						position,
						duration,
						completed_chapters: storedVideoProgress.items || {},
						total_chapters: storedVideoProgress.totalItems ?? Object.keys(storedVideoProgress.items || {}).length,
						completed_chapters_count: storedVideoProgress.completedItems ?? 0,
					}

					dispatchProgressUpdated(videoId, percentage, metadata)
				},

				// ========== PREFERENCES SLICE ==========
				preferences: {
					theme: "system",
					selfAssessmentEnabled: false,
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

				getAssistantPreferences: () => {
					const { assistantSidebarPinned, assistantModel, assistantSidebarWidth } = get().preferences
					return {
						sidebarPinned: assistantSidebarPinned,
						model: assistantModel,
						sidebarWidth: assistantSidebarWidth,
					}
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
						progress: state.books.progress,
						readingState: state.books.readingState,
					},
					videos: {
						progress: state.videos.progress,
						playbackState: state.videos.playbackState,
					},
					preferences: state.preferences,
				}),
				version: 5,
				migrate: (persistedState, version) => {
					// Migration from version 4 to 5 - remove unused courses slice
					if (version === 4) {
						delete persistedState.courses
					}

					// Migration from version 3 to 4 - standardize progress structure
					if (version === 3) {
						// Migrate course data to new structure
						if (persistedState.course) {
							persistedState.courses = {
								progress: persistedState.course.progressStats || {},
								loading: {},
								error: {},
								activeCourseId: persistedState.course.activeCourseId || null,
								lastViewedCourseId: persistedState.course.lastViewedCourseId || null,
							}

							// Convert old lesson completion to standardized progress
							if (persistedState.course.lessonCompletion) {
								for (const [courseId, lessons] of Object.entries(persistedState.course.lessonCompletion)) {
									const items = lessons || {}
									const completedItems = Object.values(items).filter(Boolean).length
									const totalItems = Object.keys(items).length
									const percentage = totalItems > 0 ? Math.round((completedItems / totalItems) * 100) : 0

									persistedState.courses.progress[courseId] = {
										percentage,
										totalItems,
										completedItems,
										items,
										lastUpdated: Date.now(),
									}
								}
							}
							delete persistedState.course
						}

						// Migrate book data to new structure
						if (persistedState.books) {
							const oldBooks = persistedState.books
							persistedState.books = {
								progress: {},
								loading: {},
								error: {},
								metadata: oldBooks.metadata || {},
								readingState: oldBooks.progress || {},
							}

							// Convert old toc progress to standardized progress
							if (oldBooks.tocProgress) {
								for (const [bookId, tocItems] of Object.entries(oldBooks.tocProgress)) {
									const items = tocItems || {}
									const completedItems = Object.values(items).filter(Boolean).length
									const book = oldBooks.metadata?.[bookId]
									let totalItems = 0
									if (book?.tableOfContents) {
										const getAllChapters = (chapters, seenIds = new Set()) => {
											const allChapters = []
											for (const chapter of chapters) {
												if (!seenIds.has(chapter.id)) {
													allChapters.push(chapter)
													seenIds.add(chapter.id)
												}
												if (chapter.children && chapter.children.length > 0) {
													const childChapters = getAllChapters(chapter.children, seenIds)
													allChapters.push(...childChapters)
												}
											}
											return allChapters
										}
										const allChapters = getAllChapters(
											Array.isArray(book.tableOfContents) ? book.tableOfContents : [book.tableOfContents]
										)
										totalItems = allChapters.length
									}

									const percentage = totalItems > 0 ? Math.round((completedItems / totalItems) * 100) : 0

									persistedState.books.progress[bookId] = {
										percentage,
										totalItems,
										completedItems,
										items,
										lastUpdated: Date.now(),
									}
								}
							}
						}

						// Migrate video data to new structure
						if (persistedState.videos) {
							const oldVideos = persistedState.videos
							persistedState.videos = {
								progress: {},
								loading: {},
								error: {},
								metadata: oldVideos.metadata || {},
								playbackState: oldVideos.progress || {},
							}

							// Convert old chapter completion to standardized progress
							if (oldVideos.chapterCompletion) {
								for (const [videoId, chapters] of Object.entries(oldVideos.chapterCompletion)) {
									const items = chapters || {}
									const completedItems = Object.values(items).filter(Boolean).length
									const totalItems = Object.keys(items).length
									const percentage = totalItems > 0 ? Math.round((completedItems / totalItems) * 100) : 0

									persistedState.videos.progress[videoId] = {
										percentage,
										totalItems,
										completedItems,
										items,
										lastUpdated: Date.now(),
									}
								}
							}
						}

						// Remove courses slice after migration from 3 to 4
						delete persistedState.courses
					}

					// Previous migrations
					if (version === 0 || version === 1) {
						// Ensure course.lessonCompletion exists
						if (persistedState.course && !persistedState.course.lessonCompletion) {
							persistedState.course.lessonCompletion = {}
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
