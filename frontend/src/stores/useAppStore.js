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
	token: null,
	isAuthenticated: false,
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
				// Authentication state
				token: DEFAULT_AUTH_STATE.token,
				isAuthenticated: DEFAULT_AUTH_STATE.isAuthenticated,
				user: DEFAULT_AUTH_STATE.user,

				// Authentication actions
				setToken: (token) =>
					set((state) => {
						state.token = token;
						state.isAuthenticated = !!token;
					}),
				clearToken: () =>
					set((state) => {
						state.token = null;
						state.isAuthenticated = false;
					}),
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
					// Book progress: bookId -> { currentPage, totalPages, zoomLevel, scrollPosition, epubState }
					progress: {},
					// Book metadata cache
					metadata: {},
					// Chapter completion: bookId -> { chapterId -> completed }
					chapterCompletion: {},
					// Table of Contents progress: bookId -> { sectionId -> completed }
					tocProgress: {},
					// Progress statistics cache: bookId -> { totalSections, completedSections, percentage }
					progressStats: {},
				},

				// Book actions
				updateBookProgress: (bookId, progress, skipSync = false) => {
					set((state) => {
						state.books.progress[bookId] = {
							...state.books.progress[bookId],
							...progress,
							lastUpdated: Date.now(),
						};
					});

					// Sync to API with debounce (skip during initialization)
					if (!skipSync) {
						syncToAPI("books", bookId, { progress });
					}
				},

				updateBookChapterStatus: (bookId, chapterId, completed) => {
					set((state) => {
						if (!state.books.chapterCompletion[bookId]) {
							state.books.chapterCompletion[bookId] = {};
						}
						state.books.chapterCompletion[bookId][chapterId] = completed;
					});
					// Sync to API
					syncToAPI("books", bookId, {
						chapterStatus: { chapterId, completed },
					});
				},

				getBookProgress: (bookId) => {
					return get().books.progress[bookId] || DEFAULT_BOOK_PROGRESS;
				},

				// ========== EPUB SPECIFIC ACTIONS ==========

				updateEpubLocation: (bookId, location) => {
					set((state) => {
						if (!state.books.progress[bookId]) {
							state.books.progress[bookId] = {};
						}
						if (!state.books.progress[bookId].epubState) {
							state.books.progress[bookId].epubState = {};
						}
						state.books.progress[bookId].epubState.location = location;
						state.books.progress[bookId].epubState.lastUpdated = Date.now();
					});
					// Sync to API
					syncToAPI("books", bookId, {
						epubLocation: location,
					});
				},

				updateEpubFontSize: (bookId, fontSize) => {
					set((state) => {
						if (!state.books.progress[bookId]) {
							state.books.progress[bookId] = {};
						}
						if (!state.books.progress[bookId].epubState) {
							state.books.progress[bookId].epubState = {};
						}
						state.books.progress[bookId].epubState.fontSize = fontSize;
					});
					// Sync to API
					syncToAPI("books", bookId, {
						epubFontSize: fontSize,
					});
				},

				getEpubState: (bookId) => {
					return (
						get().books.progress[bookId]?.epubState || {
							location: null,
							fontSize: 100,
							lastUpdated: null,
						}
					);
				},

				// ========== TABLE OF CONTENTS ACTIONS ==========

				updateTocSectionProgress: (bookId, sectionId, isCompleted) => {
					set((state) => {
						if (!state.books.tocProgress[bookId]) {
							state.books.tocProgress[bookId] = {};
						}
						state.books.tocProgress[bookId][sectionId] = isCompleted;
					});
					// Recalculate and cache progress stats
					const state = get();
					state.recalculateBookProgressStats(bookId);
					// Sync the entire tocProgress object to the API
					const tocProgress = state.books.tocProgress[bookId];
					syncToAPI("books", bookId, {
						tocProgress,
					});
				},

				batchUpdateTocProgress: (bookId, updates, skipSync = false) => {
					set((state) => {
						if (!state.books.tocProgress[bookId]) {
							state.books.tocProgress[bookId] = {};
						}

						// Apply all updates at once
						for (const { sectionId, isCompleted } of updates) {
							state.books.tocProgress[bookId][sectionId] = isCompleted;
						}
					});
					// Recalculate stats after batch update
					get().recalculateBookProgressStats(bookId);
					// Batch sync to API only if not skipped (e.g., during migration)
					if (!skipSync) {
						const tocProgress = get().books.tocProgress[bookId];
						syncToAPI("books", bookId, {
							tocProgress,
						});
					}
				},

				// Note: getTocProgress and getCompletedSections removed to prevent infinite loops
				// Use direct access: state.books.tocProgress[bookId] || {}
				// For completedSections, use useMemo in components

				// Calculate progress from table of contents - simple and dead simple approach
				calculateTocProgress: (bookId, tableOfContents) => {
					if (!tableOfContents)
						return { totalSections: 0, completedSections: 0, percentage: 0 };

					const tocProgress = get().books.tocProgress[bookId] || {};
					const completedSections = new Set(
						Object.entries(tocProgress)
							.filter(([_, completed]) => completed)
							.map(([sectionId, _]) => sectionId),
					);

					// Simple approach: count ALL chapters and sections (flatten the structure)
					// BUT deduplicate by ID to handle duplicate entries in ToC
					const getAllChapters = (chapters, seenIds = new Set()) => {
						const allChapters = [];

						for (const chapter of chapters) {
							// Only add if we haven't seen this ID before
							if (!seenIds.has(chapter.id)) {
								allChapters.push(chapter);
								seenIds.add(chapter.id);
							}
							// If it has children, process them recursively with the same seenIds set
							if (chapter.children && chapter.children.length > 0) {
								const childChapters = getAllChapters(chapter.children, seenIds);
								allChapters.push(...childChapters);
							}
						}
						return allChapters;
					};

					const allChapters = getAllChapters(
						Array.isArray(tableOfContents)
							? tableOfContents
							: [tableOfContents],
					);

					const totalChapters = allChapters.length;
					const completedChapters = allChapters.filter((chapter) =>
						completedSections.has(chapter.id),
					).length;

					// Simple rule: if all chapters are done, show 100%
					let percentage = 0;
					if (totalChapters > 0) {
						if (completedChapters === totalChapters) {
							percentage = 100;
						} else {
							percentage = Math.round(
								(completedChapters / totalChapters) * 100,
							);
						}
					}

					// Debug logging for the specific problematic book
					if (bookId === "161320ce-b579-49e3-897f-b7ab95d24af5") {
						console.log(`📊 SIMPLE Progress calculation for book ${bookId}:`, {
							totalChapters,
							completedChapters,
							percentage,
							allChaptersDone: completedChapters === totalChapters,
							completedSectionsIds: Array.from(completedSections),
							allChapterIds: allChapters.map((c) => c.id),
						});
					}

					return {
						totalSections: totalChapters,
						completedSections: completedChapters,
						percentage,
						lastUpdated: Date.now(),
					};
				},

				// Recalculate and cache progress stats
				recalculateBookProgressStats: (bookId) => {
					const book = get().books.metadata[bookId];
					if (!book?.tableOfContents) return;

					const stats = get().calculateTocProgress(
						bookId,
						book.tableOfContents,
					);
					set((state) => {
						state.books.progressStats[bookId] = {
							...stats,
							type: "toc-based",
							bookId,
						};
					});

					// Emit custom event for components listening to progress changes
					if (typeof window !== "undefined") {
						window.dispatchEvent(
							new CustomEvent("bookProgressUpdate", {
								detail: { bookId, stats },
							}),
						);
					}

					return stats;
				},

				// Force refresh progress stats (clear cache and recalculate)
				forceRefreshBookProgress: (bookId) => {
					set((state) => {
						// Clear cached progress stats to force fresh calculation
						delete state.books.progressStats[bookId];
					});
					return get().recalculateBookProgressStats(bookId);
				},

				// Note: getBookProgressStats removed to prevent infinite loops
				// Use direct access: state.books.progressStats[bookId] || defaultObject

				// Initialize ToC progress from book data
				initializeTocProgress: (bookId, book) => {
					if (!book?.tableOfContents) return;
					// Store book metadata for progress calculations
					set((state) => {
						state.books.metadata[bookId] = book;
					});
					// Initialize ToC progress from server data if available
					if (book.progress?.tocProgress) {
						set((state) => {
							state.books.tocProgress[bookId] = book.progress.tocProgress;
						});
					} else if (!get().books.tocProgress[bookId]) {
						// Initialize empty progress if none exists
						set((state) => {
							state.books.tocProgress[bookId] = {};
						});
					}

					// Calculate initial stats
					get().recalculateBookProgressStats(bookId);
				},

				// ========== VIDEOS SLICE ==========
				videos: {
					// Video progress: videoId -> { currentTime, duration, playbackRate, volume }
					progress: {},
					// Video metadata cache
					metadata: {},
					// Video chapter completion: videoId -> { chapterId -> completed }
					chapterCompletion: {},
				},

				// Video actions
				updateVideoProgress: (videoId, progress) => {
					set((state) => {
						state.videos.progress[videoId] = {
							...state.videos.progress[videoId],
							...progress,
							lastUpdated: Date.now(),
						};
					});
					// Sync to API with debounce
					syncToAPI("videos", videoId, { progress });
				},

				getVideoProgress: (videoId) => {
					return get().videos.progress[videoId] || DEFAULT_VIDEO_PROGRESS;
				},

				updateVideoChapterCompletion: (videoId, chapterCompletion) => {
					set((state) => {
						state.videos.chapterCompletion[videoId] = {
							...state.videos.chapterCompletion[videoId],
							...chapterCompletion,
						};
					});

					// Sync to API
					syncToAPI("videos", videoId, {
						chapterCompletion,
					});
				},

				setVideoChapterStatus: (videoId, chapterId, completed) => {
					set((state) => {
						if (!state.videos.chapterCompletion[videoId]) {
							state.videos.chapterCompletion[videoId] = {};
						}
						state.videos.chapterCompletion[videoId][chapterId] = completed;
					});
					// Sync to API
					syncToAPI("videos", videoId, {
						chapterStatus: { chapterId, completed },
					});
				},

				getVideoChapterCompletion: (videoId) => {
					return get().videos.chapterCompletion[videoId] || {};
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

				// ========== COURSE INTEGRATION ==========
				// Lightweight course integration for basic tracking
				course: {
					// Currently active course ID (maps to useCourseStore)
					activeCourseId: null,
					// Last viewed course for restoration
					lastViewedCourseId: null,
					// Lesson completion: courseId -> { lessonId -> completed }
					lessonCompletion: {},
					// Course progress cache: courseId -> { completion_percentage, total_lessons, completed_lessons }
					progressStats: {},
				},

				// Course integration actions
				setActiveCourse: (courseId) => {
					set((state) => {
						state.course.activeCourseId = courseId;
						if (courseId) {
							state.course.lastViewedCourseId = courseId;
						}
					});

					// Forward to course store if available
					if (typeof window !== "undefined" && window.__courseStore) {
						window.__courseStore.getState().setActiveCourse(courseId);
					}
				},

				getActiveCourse: () => {
					return get().course.activeCourseId;
				},

				setCourseLessonStatus: (courseId, lessonId, completed) => {
					set((state) => {
						// Ensure lessonCompletion object exists
						if (!state.course.lessonCompletion) {
							state.course.lessonCompletion = {};
						}
						if (!state.course.lessonCompletion[courseId]) {
							state.course.lessonCompletion[courseId] = {};
						}
						state.course.lessonCompletion[courseId][lessonId] = completed;
					});
					// Note: API sync is handled by the updateLessonStatus call in useProgress hook
				},

				getCourseLessonCompletion: (courseId) => {
					const courseData = get().course;
					if (!courseData || !courseData.lessonCompletion) {
						return {};
					}
					return courseData.lessonCompletion[courseId] || {};
				},

				// Course progress tracking actions
				setCourseProgress: (courseId, progressStats) => {
					set((state) => {
						state.course.progressStats[courseId] = {
							...progressStats,
							lastUpdated: Date.now(),
						};
					});

					// Emit custom event for components listening to course progress changes
					if (typeof window !== "undefined") {
						window.dispatchEvent(
							new CustomEvent("courseProgressUpdate", {
								detail: { courseId, progressStats },
							}),
						);
					}
				},

				getCourseProgress: (courseId) => {
					return get().course.progressStats[courseId] || null;
				},

				// Force refresh course progress (clear cache and emit event)
				refreshCourseProgress: (courseId) => {
					set((state) => {
						// Clear cached progress stats to force fresh fetch
						delete state.course.progressStats[courseId];
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
							metadata: {},
							chapterCompletion: {},
							tocProgress: {},
							progressStats: {},
						};
						state.videos = {
							progress: {},
							metadata: {},
							chapterCompletion: {},
						};
						state.course = {
							activeCourseId: null,
							lastViewedCourseId: null,
							lessonCompletion: {},
							progressStats: {},
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
						// Fetch all user data from server
						const response = await fetch("/api/v1/user/state");
						if (response.ok) {
							const serverData = await response.json();
							set((state) => {
								// Merge server data with local state
								if (serverData.books) {
									state.books = { ...state.books, ...serverData.books };
								}
								if (serverData.videos) {
									state.videos = { ...state.videos, ...serverData.videos };
								}
								if (serverData.preferences) {
									state.preferences = {
										...state.preferences,
										...serverData.preferences,
									};
								}
								if (serverData.course) {
									state.course = {
										...state.course,
										...serverData.course,
									};
								}
							});
						}
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
					preferences: state.preferences,
					course: state.course,
					token: state.token,
					user: state.user,
					// Don't persist UI state
				}),
				version: 3, // Increment version to trigger migration
				migrate: (persistedState, version) => {
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
export const selectBookProgress = (bookId) => (state) =>
	state.books.progress[bookId];
export const selectVideoProgress = (videoId) => (state) =>
	state.videos.progress[videoId];
export const selectTocProgress = (bookId) => (state) =>
	state.books.tocProgress[bookId] || {};
export const selectProgressStats = (bookId) => (state) =>
	state.books.progressStats[bookId];
export const selectCourseProgress = (courseId) => (state) =>
	state.course.progressStats[courseId];

// Assistant selectors
export const selectAssistantSidebarPinned = (state) =>
	state.preferences.assistantSidebarPinned;
export const selectAssistantModel = (state) => state.preferences.assistantModel;
export const selectAssistantPreferences = (state) =>
	state.getAssistantPreferences();

export default useAppStore;
