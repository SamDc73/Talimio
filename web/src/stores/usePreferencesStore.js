/**
 * @deprecated This store is deprecated. Use useAppStore instead.
 * All state management should go through the single useAppStore to follow
 * the documented state management architecture.
 *
 * Migration guide:
 * - Book pages: use useAppStore's updateBookProgress(bookId, { currentPage })
 * - Book zoom: use useAppStore's updateBookProgress(bookId, { zoomLevel })
 * - Theme: use useAppStore's updatePreference('theme', value)
 * - EPUB locations: use useAppStore's updateEpubLocation(bookId, location)
 * - Video chapters: use useAppStore's updateVideoChapterCompletion(videoId, chapters)
 */

import { create } from "zustand";
import {
	createJSONStorage,
	persist,
	subscribeWithSelector,
} from "zustand/middleware";

// Helper to clean up old entries
const cleanupOldEntries = (state, _keyPrefix, expiryDays) => {
	const now = Date.now();
	const maxAge = expiryDays * 24 * 60 * 60 * 1000;
	const cleaned = {};

	for (const [key, value] of Object.entries(state)) {
		if (value?.timestamp && now - value.timestamp > maxAge) {
			continue; // Skip expired entries
		}
		cleaned[key] = value;
	}

	return cleaned;
};

const usePreferencesStore = create(
	subscribeWithSelector(
		persist(
			(set, get) => ({
				// Book-specific preferences
				bookPages: {}, // book-page-{bookId}
				bookZooms: {}, // book-zoom-{bookId}
				bookTocProgress: {}, // bookTocProgress_{bookId}
				epubLocations: {}, // epub-location-{bookId}

				// Video preferences
				videoChapters: {}, // video_chapters_{videoId}

				// Global preferences
				theme: "light",
				globalZoom: 100,

				// Book page methods
				setBookPage: (bookId, page) =>
					set((state) => ({
						bookPages: {
							...state.bookPages,
							[bookId]: { page, timestamp: Date.now() },
						},
					})),

				getBookPage: (bookId) => {
					const state = get();
					const data = state.bookPages[bookId];
					if (!data) return null;

					// Check 30-day expiry
					const now = Date.now();
					const maxAge = 30 * 24 * 60 * 60 * 1000;
					if (data.timestamp && now - data.timestamp > maxAge) {
						// Remove expired entry
						set((state) => {
							const { [bookId]: _, ...rest } = state.bookPages;
							return { bookPages: rest };
						});
						return null;
					}

					return data.page;
				},

				// Book zoom methods
				setBookZoom: (bookId, zoom) =>
					set((state) => ({
						bookZooms: {
							...state.bookZooms,
							[bookId]: zoom,
						},
					})),

				getBookZoom: (bookId) => {
					const state = get();
					return state.bookZooms[bookId] || state.globalZoom;
				},

				setGlobalZoom: (zoom) => set({ globalZoom: zoom }),

				// Book TOC progress methods
				setBookTocProgress: (bookId, progress) =>
					set((state) => ({
						bookTocProgress: {
							...state.bookTocProgress,
							[bookId]: progress,
						},
					})),

				getBookTocProgress: (bookId) => get().bookTocProgress[bookId] || {},

				// EPUB location methods
				setEpubLocation: (bookId, location) =>
					set((state) => ({
						epubLocations: {
							...state.epubLocations,
							[bookId]: location,
						},
					})),

				getEpubLocation: (bookId) => get().epubLocations[bookId] || null,

				// Video chapter methods
				setVideoChapters: (videoId, chapters) =>
					set((state) => ({
						videoChapters: {
							...state.videoChapters,
							[videoId]: chapters,
						},
					})),

				getVideoChapters: (videoId) => get().videoChapters[videoId] || [],

				// Theme methods
				setTheme: (theme) => set({ theme }),

				// Cleanup methods
				cleanupBookPages: () =>
					set((state) => ({
						bookPages: cleanupOldEntries(state.bookPages, "book-page", 30),
					})),

				clearBookPreferences: (bookId) =>
					set((state) => {
						const { [bookId]: _1, ...bookPages } = state.bookPages;
						const { [bookId]: _2, ...bookZooms } = state.bookZooms;
						const { [bookId]: _3, ...bookTocProgress } = state.bookTocProgress;
						const { [bookId]: _4, ...epubLocations } = state.epubLocations;

						return {
							bookPages,
							bookZooms,
							bookTocProgress,
							epubLocations,
						};
					}),

				// Clear all preferences
				clearAll: () =>
					set({
						bookPages: {},
						bookZooms: {},
						bookTocProgress: {},
						epubLocations: {},
						videoChapters: {},
						theme: "light",
						globalZoom: 100,
					}),
			}),
			{
				name: "user-preferences",
				storage: createJSONStorage(() => localStorage),
				partialize: (state) => ({
					// Only persist what we need
					bookPages: state.bookPages,
					bookZooms: state.bookZooms,
					bookTocProgress: state.bookTocProgress,
					epubLocations: state.epubLocations,
					videoChapters: state.videoChapters,
					theme: state.theme,
					globalZoom: state.globalZoom,
				}),
				onRehydrateStorage: (_state) => {
					return (state, error) => {
						if (!error && state) {
							// Clean up expired entries on load
							state.cleanupBookPages();
						}
					};
				},
			},
		),
	),
);

// Convenience hooks for specific features
export const useBookPage = (bookId) => {
	const getBookPage = usePreferencesStore((state) => state.getBookPage);
	const setBookPage = usePreferencesStore((state) => state.setBookPage);
	return {
		page: getBookPage(bookId),
		setPage: (page) => setBookPage(bookId, page),
	};
};

export const useBookZoom = (bookId) => {
	const getBookZoom = usePreferencesStore((state) => state.getBookZoom);
	const setBookZoom = usePreferencesStore((state) => state.setBookZoom);
	const globalZoom = usePreferencesStore((state) => state.globalZoom);
	return {
		zoom: getBookZoom(bookId),
		setZoom: (zoom) => setBookZoom(bookId, zoom),
		globalZoom,
	};
};

export const useTheme = () => {
	const theme = usePreferencesStore((state) => state.theme);
	const setTheme = usePreferencesStore((state) => state.setTheme);
	return { theme, setTheme };
};

export default usePreferencesStore;
