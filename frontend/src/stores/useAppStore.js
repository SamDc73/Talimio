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

/**
 * Main application store with all state slices
 * Single source of truth for client-side state
 */
const useAppStore = create(
	devtools(
		persist(
			immer((set, get) => ({
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
					// Sync to API (if endpoint exists)
					syncToAPI("books", bookId, {
						tocProgress: { sectionId, isCompleted },
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
					const state = get();
					state.recalculateBookProgressStats(bookId);
					// Batch sync to API only if not skipped (e.g., during migration)
					if (!skipSync) {
						syncToAPI("books", bookId, {
							tocProgressBatch: updates,
						});
					}
				},

				// Note: getTocProgress and getCompletedSections removed to prevent infinite loops
				// Use direct access: state.books.tocProgress[bookId] || {}
				// For completedSections, use useMemo in components

				// Calculate progress from table of contents
				calculateTocProgress: (bookId, tableOfContents) => {
					if (!tableOfContents)
						return { totalSections: 0, completedSections: 0, percentage: 0 };
					const tocProgress = get().books.tocProgress[bookId] || {};
					const completedSections = new Set(
						Object.entries(tocProgress)
							.filter(([_, completed]) => completed)
							.map(([sectionId, _]) => sectionId),
					);

					const countSections = (chapters) => {
						let total = 0;
						let completed = 0;
						for (const chapter of chapters) {
							if (chapter.children && chapter.children.length > 0) {
								const [subTotal, subCompleted] = countSections(
									chapter.children,
								);
								total += subTotal;
								completed += subCompleted;
							} else {
								total += 1;
								if (completedSections.has(chapter.id)) {
									completed += 1;
								}
							}
						}
						return [total, completed];
					};

					const [totalSections, completed] = countSections(
						Array.isArray(tableOfContents)
							? tableOfContents
							: [tableOfContents],
					);

					const percentage =
						totalSections > 0
							? Math.round((completed / totalSections) * 100)
							: 0;

					return {
						totalSections,
						completedSections: completed,
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

				// Note: getBookProgressStats removed to prevent infinite loops
				// Use direct access: state.books.progressStats[bookId] || defaultObject

				// Initialize ToC progress from book data
				initializeTocProgress: (bookId, book) => {
					if (!book?.tableOfContents) return;
					// Store book metadata for progress calculations
					set((state) => {
						state.books.metadata[bookId] = book;
					});
					// Initialize empty progress if none exists
					if (!get().books.tocProgress[bookId]) {
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
					// Onboarding preferences
					onboardingCompleted: false,
					userPreferences: null,
					// UI preferences
					sidebarOpen: true,
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

				// ========== ROADMAPS SLICE ==========
				roadmaps: {
					// Roadmap progress: roadmapId -> { nodeId -> completed }
					nodeCompletion: {},
					// Active roadmap being viewed
					activeRoadmapId: null,
				},

				// Roadmap actions
				updateNodeCompletion: (roadmapId, nodeId, completed) => {
					set((state) => {
						if (!state.roadmaps.nodeCompletion[roadmapId]) {
							state.roadmaps.nodeCompletion[roadmapId] = {};
						}
						state.roadmaps.nodeCompletion[roadmapId][nodeId] = completed;
					});
					// Sync to API
					syncToAPI("roadmaps", roadmapId, {
						nodeStatus: { nodeId, completed },
					});
				},

				setActiveRoadmap: (roadmapId) => {
					set((state) => {
						state.roadmaps.activeRoadmapId = roadmapId;
					});
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
									key === "onboarding_preferences" ||
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
						state.roadmaps = { nodeCompletion: {}, activeRoadmapId: null };
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
								if (serverData.roadmaps) {
									state.roadmaps = {
										...state.roadmaps,
										...serverData.roadmaps,
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
					roadmaps: state.roadmaps,
					// Don't persist UI state
				}),
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

export default useAppStore;
