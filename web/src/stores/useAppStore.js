import { create } from "zustand";
import { createJSONStorage, devtools, persist } from "zustand/middleware";
import { immer } from "zustand/middleware/immer";
// API sync utilities
import { syncToAPI } from "../lib/apiSync.js";

// Stable default objects to prevent infinite re-renders
const DEFAULT_BOOK_PROGRESS = {
	currentPage: 1,
	totalPages: 0,
	zoomLevel: 100, // Changed from 1 to 100 to match percentage-based zoom
	scrollPosition: { x: 0, y: 0 },
	epubState: {
		location: null,
		fontSize: 100,
		lastUpdated: null,
	},
};
const DEFAULT_VIDEO_PROGRESS = {
	currentTime: 0,
	duration: 0,
	playbackRate: 1,
	volume: 1,
};

const DEFAULT_AUTH_STATE = {
	user: null,
};

/**
 * Main application store with all state slices
 * Single source of truth for client-side state
 */
const useAppStore = create(
	devtools(
		persist(
			immer((set, get) => ({
				// Authentication state (only user, no token - using httpOnly cookies)
				user: DEFAULT_AUTH_STATE.user,

				// Authentication actions
				setUser: (user) =>
					set((state) => {
						state.user = user;
					}),
				clearUser: () =>
					set((state) => {
						state.user = null;
					}),
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
					set((state) => {
						state.books.progress[bookId] = {
							...progress,
							lastUpdated: Date.now(),
						};
					});

					// Emit custom event for components listening to book progress changes
					if (typeof window !== "undefined") {
						window.dispatchEvent(
							new CustomEvent("bookProgressUpdate", {
								detail: { bookId, progressStats: progress },
							}),
						);
					}
				},

				// Toggle book item completion (chapters)
				toggleBookItem: (bookId, chapterId) => {
					const progress = get().books.progress[bookId] || {
						percentage: 0,
						totalItems: 0,
						completedItems: 0,
						items: {},
					};

					const wasCompleted = progress.items[chapterId] || false;
					const isCompleted = !wasCompleted;

					// Calculate new progress
					const completedItems =
						progress.completedItems + (isCompleted ? 1 : -1);
					const percentage =
						progress.totalItems > 0
							? Math.round((completedItems / progress.totalItems) * 100)
							: 0;

					const newProgress = {
						...progress,
						items: {
							...progress.items,
							[chapterId]: isCompleted,
						},
						completedItems,
						percentage,
						lastUpdated: Date.now(),
						clientId: getClientId(), // Track which client made the change
					};

					// Track this as a local update to prevent echo

					// Update optimistically
					set((state) => {
						state.books.progress[bookId] = newProgress;
					});

					// Dispatch browser event for dashboard sync
					window.dispatchEvent(
						new CustomEvent("bookProgressUpdate", {
							detail: { bookId, progressStats: newProgress },
						}),
					);
				},

				// Batch update book items
				batchUpdateBook: (bookId, updates) => {
					const progress = get().books.progress[bookId] || {
						percentage: 0,
						totalItems: 0,
						completedItems: 0,
						items: {},
					};

					// Apply all updates
					const newItems = { ...progress.items };
					for (const { itemId, completed } of updates) {
						newItems[itemId] = completed;
					}

					// Calculate new progress
					const completedItems = Object.values(newItems).filter(Boolean).length;
					const percentage =
						progress.totalItems > 0
							? Math.round((completedItems / progress.totalItems) * 100)
							: 0;

					const newProgress = {
						...progress,
						items: newItems,
						completedItems,
						percentage,
						lastUpdated: Date.now(),
						clientId: getClientId(), // Track which client made the change
					};

					// Track this as a local update to prevent echo

					// Update state
					set((state) => {
						state.books.progress[bookId] = newProgress;
					});

					// Dispatch browser event
					window.dispatchEvent(
						new CustomEvent("bookProgressUpdate", {
							detail: { bookId, progressStats: newProgress },
						}),
					);
				},

				// Set book loading state
				setBookLoading: (bookId, isLoading) => {
					set((state) => {
						state.books.loading[bookId] = isLoading;
					});
				},

				// Set book error state
				setBookError: (bookId, error) => {
					set((state) => {
						state.books.error[bookId] = error;
					});
				},

				// Get book progress
				getBookProgress: (bookId) => {
					return get().books.progress[bookId] || null;
				},

				// Reading state management (separate from progress)
				updateBookReadingState: (bookId, readingState, skipSync = false) => {
					console.log(`🏪 [Store] updateBookReadingState called:`, {
						bookId,
						readingState,
						skipSync,
					});
					// Check if the state has actually changed
					const currentState = get().books.readingState[bookId];
					console.log(`🏪 [Store] Current state:`, currentState);
					const hasChanged =
						!currentState ||
						(readingState.currentPage !== undefined &&
							readingState.currentPage !== currentState.currentPage) ||
						(readingState.zoomLevel !== undefined &&
							readingState.zoomLevel !== currentState.zoomLevel) ||
						(readingState.scrollPosition !== undefined &&
							(readingState.scrollPosition.x !==
								currentState.scrollPosition?.x ||
								readingState.scrollPosition.y !==
									currentState.scrollPosition?.y));

					console.log(`🏪 [Store] Has changed: ${hasChanged}`);
					if (!hasChanged) {
						console.log(`🏪 [Store] No change detected, skipping update`);
						return; // No change, don't update
					}

					console.log(`🏪 [Store] Updating state...`);
					set((state) => {
						state.books.readingState[bookId] = {
							...state.books.readingState[bookId],
							...readingState,
							lastUpdated: Date.now(),
						};
					});

					// Sync to API with debounce (skip during initialization)
					if (!skipSync) {
						console.log(`🏪 [Store] Calling syncToAPI...`);
						syncToAPI("books", bookId, { readingState });
					} else {
						console.log(`🏪 [Store] Skipping sync (skipSync=true)`);
					}
				},

				getBookReadingState: (bookId) => {
					return get().books.readingState[bookId] || DEFAULT_BOOK_PROGRESS;
				},

				setBookZoom: (bookId, zoomLevel) => {
					set((state) => {
						if (!state.books.readingState[bookId]) {
							state.books.readingState[bookId] = { ...DEFAULT_BOOK_PROGRESS };
						}
						state.books.readingState[bookId].zoomLevel = zoomLevel;
						state.books.readingState[bookId].lastUpdated = Date.now();
					});
					// Sync to API
					syncToAPI("books", bookId, { readingState: { zoomLevel } });
				},

				// ========== EPUB SPECIFIC ACTIONS ==========

				updateEpubLocation: (bookId, location) => {
					set((state) => {
						if (!state.books.readingState[bookId]) {
							state.books.readingState[bookId] = {};
						}
						if (!state.books.readingState[bookId].epubState) {
							state.books.readingState[bookId].epubState = {};
						}
						state.books.readingState[bookId].epubState.location = location;
						state.books.readingState[bookId].epubState.lastUpdated = Date.now();
					});
					// Sync to API
					syncToAPI("books", bookId, {
						epubLocation: location,
					});
				},

				updateEpubFontSize: (bookId, fontSize) => {
					set((state) => {
						if (!state.books.readingState[bookId]) {
							state.books.readingState[bookId] = {};
						}
						if (!state.books.readingState[bookId].epubState) {
							state.books.readingState[bookId].epubState = {};
						}
						state.books.readingState[bookId].epubState.fontSize = fontSize;
					});
					// Sync to API
					syncToAPI("books", bookId, {
						epubFontSize: fontSize,
					});
				},

				getEpubState: (bookId) => {
					return (
						get().books.readingState[bookId]?.epubState || {
							location: null,
							fontSize: 100,
							lastUpdated: null,
						}
					);
				},

				// Initialize book progress from book data
				initializeBookProgress: (bookId, book) => {
					console.log(`📚 initializeBookProgress called for book ${bookId}`, {
						hasToC: !!book?.tableOfContents,
						tocLength: book?.tableOfContents?.length,
						hasProgress: !!book?.progress,
					});

					if (!book?.tableOfContents) {
						console.warn(`❌ No table of contents for book ${bookId}`);
						return;
					}

					// Store book metadata for progress calculations
					set((state) => {
						state.books.metadata[bookId] = {
							...book,
							tableOfContents: book.tableOfContents,
						};
					});

					// Count only leaf chapters (not parent chapters)
					const getAllLeafChapters = (chapters, seenIds = new Set()) => {
						const leafChapters = [];
						for (const chapter of chapters) {
							if (!seenIds.has(chapter.id)) {
								seenIds.add(chapter.id);
								if (chapter.children && chapter.children.length > 0) {
									// Parent chapter - recurse into children
									const childChapters = getAllLeafChapters(
										chapter.children,
										seenIds,
									);
									leafChapters.push(...childChapters);
								} else {
									// Leaf chapter - add to list
									leafChapters.push(chapter);
								}
							}
						}
						return leafChapters;
					};

					const leafChapters = getAllLeafChapters(
						Array.isArray(book.tableOfContents)
							? book.tableOfContents
							: [book.tableOfContents],
					);

					// Initialize standardized progress from server data if available
					const items = {};
					if (book.progress?.tocProgress) {
						for (const [chapterId, completed] of Object.entries(
							book.progress.tocProgress,
						)) {
							items[chapterId] = completed;
						}
					}

					// Count only completed leaf chapters
					const completedLeafIds = new Set();
					for (const leafChapter of leafChapters) {
						if (items[leafChapter.id]) {
							completedLeafIds.add(leafChapter.id);
						}
					}

					const completedItems = completedLeafIds.size;
					const totalItems = leafChapters.length;
					const percentage =
						totalItems > 0
							? Math.round((completedItems / totalItems) * 100)
							: 0;

					const progress = {
						percentage,
						totalItems,
						completedItems,
						items,
						lastUpdated: Date.now(),
					};

					// Set standardized progress
					set((state) => {
						state.books.progress[bookId] = progress;
					});

					console.log(`✅ Initialized book progress for ${bookId}:`, progress);
				},

				// ========== VIDEOS SLICE ==========
				videos: {
					// Video progress: videoId -> { percentage, totalItems, completedItems, items, lastUpdated }
					progress: {},
					// Loading states: videoId -> boolean
					loading: {},
					// Error states: videoId -> Error | null
					error: {},
					// Video metadata cache
					metadata: {},
					// Video playback state: videoId -> { currentTime, duration, playbackRate, volume }
					playbackState: {},
				},

				// ========== VIDEO ACTIONS ==========
				// Standardized actions matching course/book patterns

				// Set video progress
				setVideoProgress: (videoId, progress) => {
					// Track this as a local update to prevent echo

					set((state) => {
						state.videos.progress[videoId] = {
							...progress,
							lastUpdated: Date.now(),
						};
					});

					// Emit custom event for components listening to video progress changes
					if (typeof window !== "undefined") {
						window.dispatchEvent(
							new CustomEvent("videoProgressUpdate", {
								detail: { videoId, progress },
							}),
						);
					}
				},

				// Toggle video item completion (chapters)
				toggleVideoItem: (videoId, chapterId) => {
					const progress = get().videos.progress[videoId] || {
						percentage: 0,
						totalItems: 0,
						completedItems: 0,
						items: {},
					};

					const wasCompleted = progress.items[chapterId] || false;
					const isCompleted = !wasCompleted;

					// Calculate new progress
					const completedItems =
						progress.completedItems + (isCompleted ? 1 : -1);
					const percentage =
						progress.totalItems > 0
							? Math.round((completedItems / progress.totalItems) * 100)
							: 0;

					const newProgress = {
						...progress,
						items: {
							...progress.items,
							[chapterId]: isCompleted,
						},
						completedItems,
						percentage,
						lastUpdated: Date.now(),
						clientId: getClientId(), // Track which client made the change
					};

					// Track this as a local update to prevent echo

					// Update optimistically
					set((state) => {
						state.videos.progress[videoId] = newProgress;
					});

					// Dispatch browser event for dashboard sync
					window.dispatchEvent(
						new CustomEvent("videoProgressUpdate", {
							detail: { videoId, progress: newProgress },
						}),
					);
				},

				// Batch update video items
				batchUpdateVideo: (videoId, updates) => {
					const progress = get().videos.progress[videoId] || {
						percentage: 0,
						totalItems: 0,
						completedItems: 0,
						items: {},
					};

					// Apply all updates
					const newItems = { ...progress.items };
					for (const { itemId, completed } of updates) {
						newItems[itemId] = completed;
					}

					// Calculate new progress
					const completedItems = Object.values(newItems).filter(Boolean).length;
					const percentage =
						progress.totalItems > 0
							? Math.round((completedItems / progress.totalItems) * 100)
							: 0;

					const newProgress = {
						...progress,
						items: newItems,
						completedItems,
						percentage,
						lastUpdated: Date.now(),
						clientId: getClientId(), // Track which client made the change
					};

					// Track this as a local update to prevent echo

					// Update state
					set((state) => {
						state.videos.progress[videoId] = newProgress;
					});

					// Dispatch browser event
					window.dispatchEvent(
						new CustomEvent("videoProgressUpdate", {
							detail: { videoId, progress: newProgress },
						}),
					);
				},

				// Set video loading state
				setVideoLoading: (videoId, isLoading) => {
					set((state) => {
						state.videos.loading[videoId] = isLoading;
					});
				},

				// Set video error state
				setVideoError: (videoId, error) => {
					set((state) => {
						state.videos.error[videoId] = error;
					});
				},

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
					);
				},

				// Playback state management (separate from progress)
				updateVideoPlaybackState: (videoId, playbackState) => {
					set((state) => {
						state.videos.playbackState[videoId] = {
							...state.videos.playbackState[videoId],
							...playbackState,
							lastUpdated: Date.now(),
						};
					});
					// Sync to API with debounce
					syncToAPI("videos", videoId, { playbackState });
				},

				getVideoPlaybackState: (videoId) => {
					return get().videos.playbackState[videoId] || DEFAULT_VIDEO_PROGRESS;
				},

				// Video progress update (used by VideoViewer)
				updateVideoProgress: (videoId, progressData) => {
					// Track this as a local update to prevent echo

					// Update playback state
					set((state) => {
						state.videos.playbackState[videoId] = {
							...state.videos.playbackState[videoId],
							currentTime: progressData.lastPosition || 0,
							lastUpdated: Date.now(),
						};
					});

					// Sync to API with proper format
					syncToAPI("videos", videoId, {
						progress: {
							lastPosition: progressData.lastPosition || 0,
							completionPercentage: progressData.percentage || 0,
						},
					});

					// Also dispatch event for real-time updates
					window.dispatchEvent(
						new CustomEvent("videoProgressUpdate", {
							detail: {
								videoId,
								progressStats: {
									percentage: progressData.percentage || 0,
									// Keep other progress data if available
									completed_items:
										get().videos.progress[videoId]?.completedItems || 0,
									total_items: get().videos.progress[videoId]?.totalItems || 0,
								},
							},
						}),
					);
				},

				// ========== FLASHCARDS SLICE ==========
				flashcards: {
					// Flashcard progress: deckId -> { lastCard, settings }
					progress: {},
					// Flashcard metadata cache
					metadata: {},
					// Progress statistics cache: deckId -> { percentage, reviewed, total, due, overdue }
					progressStats: {},
				},

				// Flashcard actions
				updateFlashcardProgress: (deckId, progress) => {
					set((state) => {
						state.flashcards.progress[deckId] = {
							...state.flashcards.progress[deckId],
							...progress,
							lastUpdated: Date.now(),
						};
					});
					// Sync to API with debounce
					syncToAPI("flashcards", deckId, { progress });
				},

				getFlashcardProgress: (deckId) => {
					return get().flashcards.progress[deckId] || {};
				},

				setFlashcardProgressStats: (deckId, stats) => {
					set((state) => {
						state.flashcards.progressStats[deckId] = {
							...stats,
							lastUpdated: Date.now(),
						};
					});
				},

				getFlashcardProgressStats: (deckId) => {
					return get().flashcards.progressStats[deckId] || null;
				},

				// ========== PREFERENCES SLICE ==========
				preferences: {
					theme: "system",
					language: "en",
					autoPlayVideos: true,
					defaultZoomLevel: 1,
					sidebarCollapsed: false,
					notificationsEnabled: true,
					// User preferences
					userPreferences: null,
					// UI preferences
					sidebarOpen: true,
					// Assistant preferences
					assistantSidebarPinned: false,
					assistantModel: null, // Will be set from available models
					assistantSidebarWidth: 400, // Default width in pixels
				},

				// Preferences actions
				updatePreference: (key, value) => {
					set((state) => {
						state.preferences[key] = value;
					});
					// Sync preferences to API
					syncToAPI("preferences", "user", { [key]: value });
				},

				toggleTheme: () => {
					const current = get().preferences.theme;
					const next =
						current === "light"
							? "dark"
							: current === "dark"
								? "system"
								: "light";
					get().updatePreference("theme", next);
				},

				// Assistant preference actions
				toggleAssistantSidebarPin: () => {
					const current = get().preferences.assistantSidebarPinned;
					get().updatePreference("assistantSidebarPinned", !current);
				},

				setAssistantModel: (modelId) => {
					get().updatePreference("assistantModel", modelId);
				},

				setAssistantSidebarWidth: (width) => {
					// Ensure width is within reasonable bounds
					const clampedWidth = Math.max(300, Math.min(800, width));
					get().updatePreference("assistantSidebarWidth", clampedWidth);
				},

				getAssistantPreferences: () => {
					const {
						assistantSidebarPinned,
						assistantModel,
						assistantSidebarWidth,
					} = get().preferences;
					return {
						sidebarPinned: assistantSidebarPinned,
						model: assistantModel,
						sidebarWidth: assistantSidebarWidth,
					};
				},

				// ========== UI SLICE ==========
				ui: {
					// Sidebar states
					sidebarOpen: true,
					activeSidebarSection: null,

					// Modal/dialog states
					activeModal: null,
					modalData: null,

					// Loading states
					loading: {},

					// Error states
					errors: [],
				},

				// UI actions
				toggleSidebar: () => {
					set((state) => {
						state.preferences.sidebarOpen = !state.preferences.sidebarOpen;
					});
				},

				setActiveModal: (modalName, data = null) => {
					set((state) => {
						state.ui.activeModal = modalName;
						state.ui.modalData = data;
					});
				},

				closeModal: () => {
					set((state) => {
						state.ui.activeModal = null;
						state.ui.modalData = null;
					});
				},

				setLoading: (key, isLoading) => {
					set((state) => {
						if (isLoading) {
							state.ui.loading[key] = true;
						} else {
							delete state.ui.loading[key];
						}
					});
				},

				addError: (error) => {
					set((state) => {
						state.ui.errors.push({
							id: Date.now(),
							message: error.message || error,
							timestamp: Date.now(),
						});
					});
				},

				removeError: (errorId) => {
					set((state) => {
						state.ui.errors = state.ui.errors.filter((e) => e.id !== errorId);
					});
				},

				// ========== COURSES SLICE ==========
				courses: {
					progress: {},
					loading: {},
					error: {},
					// Currently active course ID
					activeCourseId: null,
					// Last viewed course for restoration
					lastViewedCourseId: null,
				},

				// ========== COURSE ACTIONS ==========

				setCourseProgress: (courseId, progress) => {
					// Track this as a local update to prevent echo

					set((state) => {
						state.courses.progress[courseId] = {
							...progress,
							lastUpdated: Date.now(),
						};
					});

					if (typeof window !== "undefined") {
						window.dispatchEvent(
							new CustomEvent("courseProgressUpdate", {
								detail: { courseId, progressStats: progress },
							}),
						);
					}
				},

				toggleCourseItem: (courseId, lessonId) => {
					const progress = get().courses.progress[courseId] || {
						percentage: 0,
						totalItems: 0,
						completedItems: 0,
						items: {},
					};

					const wasCompleted = progress.items[lessonId] || false;
					const isCompleted = !wasCompleted;

					const completedItems =
						progress.completedItems + (isCompleted ? 1 : -1);
					const percentage =
						progress.totalItems > 0
							? Math.round((completedItems / progress.totalItems) * 100)
							: 0;

					const newProgress = {
						...progress,
						items: {
							...progress.items,
							[lessonId]: isCompleted,
						},
						completedItems,
						percentage,
						lastUpdated: Date.now(),
						clientId: getClientId(), // Track which client made the change
					};

					set((state) => {
						state.courses.progress[courseId] = newProgress;
					});

					window.dispatchEvent(
						new CustomEvent("courseProgressUpdate", {
							detail: { courseId, progressStats: newProgress },
						}),
					);
				},

				// Batch update course items
				batchUpdateCourse: (courseId, updates) => {
					const progress = get().courses.progress[courseId] || {
						percentage: 0,
						totalItems: 0,
						completedItems: 0,
						items: {},
					};

					// Apply all updates
					const newItems = { ...progress.items };
					for (const { itemId, completed } of updates) {
						newItems[itemId] = completed;
					}

					// Calculate new progress
					const completedItems = Object.values(newItems).filter(Boolean).length;
					const percentage =
						progress.totalItems > 0
							? Math.round((completedItems / progress.totalItems) * 100)
							: 0;

					const newProgress = {
						...progress,
						items: newItems,
						completedItems,
						percentage,
						lastUpdated: Date.now(),
						clientId: getClientId(), // Track which client made the change
					};

					// Track this as a local update to prevent echo

					// Update state
					set((state) => {
						state.courses.progress[courseId] = newProgress;
					});

					// Dispatch browser event
					window.dispatchEvent(
						new CustomEvent("courseProgressUpdate", {
							detail: { courseId, progressStats: newProgress },
						}),
					);
				},

				// Set course loading state
				setCourseLoading: (courseId, isLoading) => {
					set((state) => {
						state.courses.loading[courseId] = isLoading;
					});
				},

				// Set course error state
				setCourseError: (courseId, error) => {
					set((state) => {
						state.courses.error[courseId] = error;
					});
				},

				// Get course progress
				getCourseProgress: (courseId) => {
					return get().courses.progress[courseId] || null;
				},

				// Set active course
				setActiveCourse: (courseId) => {
					set((state) => {
						state.courses.activeCourseId = courseId;
						if (courseId) {
							state.courses.lastViewedCourseId = courseId;
						}
					});
				},

				getActiveCourse: () => {
					return get().courses.activeCourseId;
				},

				// Force refresh course progress (clear cache and emit event)
				refreshCourseProgress: (courseId) => {
					set((state) => {
						// Clear cached progress stats to force fresh fetch
						delete state.courses.progress[courseId];
					});

					// Emit event to notify components to refetch
					if (typeof window !== "undefined") {
						window.dispatchEvent(
							new CustomEvent("courseProgressRefresh", {
								detail: { courseId },
							}),
						);
					}
				},

				// ========== CLEANUP ACTIONS ==========

				// Clean up old localStorage data from migration
				cleanupOldStorage: () => {
					try {
						const keysToRemove = [];
						// Find keys that match old patterns
						for (let i = 0; i < localStorage.length; i++) {
							const key = localStorage.key(i);
							if (
								key &&
								(key.startsWith("book_progress_") ||
									key.startsWith("video_progress_") ||
									key.startsWith("video_chapters_") ||
									key.startsWith("epub_location_") ||
									key.startsWith("book_page_") ||
									key.startsWith("book_zoom_") ||
									key.startsWith("toc_progress_") ||
									key === "user-preferences" || // Remove deprecated preferences store
									key.includes("USER_PREFERENCES"))
							) {
								keysToRemove.push(key);
							}
						}

						// Remove old keys
						for (const key of keysToRemove) {
							localStorage.removeItem(key);
							console.log(`Cleaned up old storage key: ${key}`);
						}
						if (keysToRemove.length > 0) {
							console.log(
								`Cleaned up ${keysToRemove.length} old localStorage keys`,
							);
						}
					} catch (error) {
						console.warn("Failed to cleanup old storage:", error);
					}
				},

				// ========== GLOBAL ACTIONS ==========

				// Clear all data (for logout/reset)
				clearAllData: () => {
					set((state) => {
						state.books = {
							progress: {},
							loading: {},
							error: {},
							metadata: {},
							readingState: {},
						};
						state.videos = {
							progress: {},
							loading: {},
							error: {},
							metadata: {},
							playbackState: {},
						};
						state.courses = {
							progress: {},
							loading: {},
							error: {},
							activeCourseId: null,
							lastViewedCourseId: null,
						};
						state.ui.errors = [];
						state.ui.loading = {};
					});
				},

				// Hydrate from server data
				hydrateFromServer: async () => {
					try {
						set((state) => {
							state.ui.loading.hydration = true;
						});
						// TODO: Implement server state hydration endpoint
						// For now, skip server hydration - app works with local state
						console.log(
							"Server state hydration disabled - using local state only",
						);
					} catch (error) {
						console.error("Failed to hydrate from server:", error);
						get().addError("Failed to sync with server");
					} finally {
						set((state) => {
							state.ui.loading.hydration = undefined;
						});
					}
				},
			})),
			{
				name: "learning-roadmap-storage",
				storage: createJSONStorage(() => localStorage),
				partialize: (state) => ({
					// Only persist these parts of the state
					books: state.books,
					videos: state.videos,
					courses: state.courses,
					flashcards: state.flashcards,
					preferences: state.preferences,
					user: state.user,
					// Don't persist UI state or tokens (using httpOnly cookies)
				}),
				version: 4, // Increment version to trigger migration
				migrate: (persistedState, version) => {
					// Migration from version 3 to 4 - standardize progress structure
					if (version === 3) {
						// Migrate course data to new structure
						if (persistedState.course) {
							persistedState.courses = {
								progress: persistedState.course.progressStats || {},
								loading: {},
								error: {},
								activeCourseId: persistedState.course.activeCourseId || null,
								lastViewedCourseId:
									persistedState.course.lastViewedCourseId || null,
							};

							// Convert old lesson completion to standardized progress
							if (persistedState.course.lessonCompletion) {
								for (const [courseId, lessons] of Object.entries(
									persistedState.course.lessonCompletion,
								)) {
									const items = lessons || {};
									const completedItems =
										Object.values(items).filter(Boolean).length;
									const totalItems = Object.keys(items).length;
									const percentage =
										totalItems > 0
											? Math.round((completedItems / totalItems) * 100)
											: 0;

									persistedState.courses.progress[courseId] = {
										percentage,
										totalItems,
										completedItems,
										items,
										lastUpdated: Date.now(),
									};
								}
							}
							delete persistedState.course;
						}

						// Migrate book data to new structure
						if (persistedState.books) {
							const oldBooks = persistedState.books;
							persistedState.books = {
								progress: {},
								loading: {},
								error: {},
								metadata: oldBooks.metadata || {},
								readingState: oldBooks.progress || {},
							};

							// Convert old toc progress to standardized progress
							if (oldBooks.tocProgress) {
								for (const [bookId, tocItems] of Object.entries(
									oldBooks.tocProgress,
								)) {
									const items = tocItems || {};
									const completedItems =
										Object.values(items).filter(Boolean).length;
									// We'll need to get totalItems from metadata
									const book = oldBooks.metadata?.[bookId];
									let totalItems = 0;
									if (book?.tableOfContents) {
										// Count all chapters
										const getAllChapters = (chapters, seenIds = new Set()) => {
											const allChapters = [];
											for (const chapter of chapters) {
												if (!seenIds.has(chapter.id)) {
													allChapters.push(chapter);
													seenIds.add(chapter.id);
												}
												if (chapter.children && chapter.children.length > 0) {
													const childChapters = getAllChapters(
														chapter.children,
														seenIds,
													);
													allChapters.push(...childChapters);
												}
											}
											return allChapters;
										};
										const allChapters = getAllChapters(
											Array.isArray(book.tableOfContents)
												? book.tableOfContents
												: [book.tableOfContents],
										);
										totalItems = allChapters.length;
									}

									const percentage =
										totalItems > 0
											? Math.round((completedItems / totalItems) * 100)
											: 0;

									persistedState.books.progress[bookId] = {
										percentage,
										totalItems,
										completedItems,
										items,
										lastUpdated: Date.now(),
									};
								}
							}
						}

						// Migrate video data to new structure
						if (persistedState.videos) {
							const oldVideos = persistedState.videos;
							persistedState.videos = {
								progress: {},
								loading: {},
								error: {},
								metadata: oldVideos.metadata || {},
								playbackState: oldVideos.progress || {},
							};

							// Convert old chapter completion to standardized progress
							if (oldVideos.chapterCompletion) {
								for (const [videoId, chapters] of Object.entries(
									oldVideos.chapterCompletion,
								)) {
									const items = chapters || {};
									const completedItems =
										Object.values(items).filter(Boolean).length;
									const totalItems = Object.keys(items).length;
									const percentage =
										totalItems > 0
											? Math.round((completedItems / totalItems) * 100)
											: 0;

									persistedState.videos.progress[videoId] = {
										percentage,
										totalItems,
										completedItems,
										items,
										lastUpdated: Date.now(),
									};
								}
							}
						}
					}

					// Previous migrations
					if (version === 0 || version === 1) {
						// Migration from version 0 or 1 to 2
						// Ensure course.lessonCompletion exists
						if (
							persistedState.course &&
							!persistedState.course.lessonCompletion
						) {
							persistedState.course.lessonCompletion = {};
						}
					}
					return persistedState;
				},
			},
		),
		{
			name: "app-store",
		},
	),
);
// Optimized selectors to prevent unnecessary re-renders
export const selectSidebarOpen = (state) => state.preferences.sidebarOpen;
export const selectToggleSidebar = (state) => state.toggleSidebar;
export const selectTheme = (state) => state.preferences.theme;
// Progress selectors - standardized interface
export const selectBookProgress = (bookId) => (state) =>
	state.books.progress[bookId];
export const selectVideoProgress = (videoId) => (state) =>
	state.videos.progress[videoId];
export const selectCourseProgress = (courseId) => (state) =>
	state.courses.progress[courseId];

// Reading state selectors
export const selectBookReadingState = (bookId) => (state) =>
	state.books.readingState[bookId];
export const selectVideoPlaybackState = (videoId) => (state) =>
	state.videos.playbackState[videoId];

// Assistant selectors
export const selectAssistantSidebarPinned = (state) =>
	state.preferences.assistantSidebarPinned;
export const selectAssistantModel = (state) => state.preferences.assistantModel;
export const selectAssistantPreferences = (state) =>
	state.getAssistantPreferences();

export default useAppStore;
