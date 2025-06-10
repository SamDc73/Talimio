/**
 * Hook for managing book page persistence with localStorage and server sync
 */
import { useCallback, useEffect, useRef } from "react";

const STORAGE_KEY_PREFIX = "book-page-";
const STORAGE_EXPIRY_DAYS = 30;

export const useBookPagePersistence = (bookId) => {
	const storageKey = `${STORAGE_KEY_PREFIX}${bookId}`;
	const syncTimeoutRef = useRef(null);

	/**
	 * Get the last saved page from localStorage
	 */
	const getLastPageFromStorage = useCallback(() => {
		try {
			const stored = localStorage.getItem(storageKey);
			if (!stored) return null;

			const data = JSON.parse(stored);

			// Check if data is expired (older than 30 days)
			const now = Date.now();
			const dataAge = now - data.timestamp;
			const maxAge = STORAGE_EXPIRY_DAYS * 24 * 60 * 60 * 1000;

			if (dataAge > maxAge) {
				localStorage.removeItem(storageKey);
				return null;
			}

			return data.page;
		} catch (error) {
			console.warn("Failed to read page from localStorage:", error);
			return null;
		}
	}, [storageKey]);

	/**
	 * Save page to localStorage immediately
	 */
	const savePageToStorage = useCallback(
		(pageNumber) => {
			try {
				const data = {
					page: pageNumber,
					timestamp: Date.now(),
				};
				localStorage.setItem(storageKey, JSON.stringify(data));
			} catch (error) {
				console.warn("Failed to save page to localStorage:", error);
			}
		},
		[storageKey],
	);

	/**
	 * Determine the initial page to load
	 * Priority: localStorage > server data > page 1
	 */
	const getInitialPage = useCallback(
		(serverCurrentPage) => {
			const localPage = getLastPageFromStorage();

			// Use localStorage if available and more recent than server
			if (localPage && localPage > 1) {
				return localPage;
			}

			// Fallback to server data
			if (serverCurrentPage && serverCurrentPage > 1) {
				return serverCurrentPage;
			}

			// Default to page 1
			return 1;
		},
		[getLastPageFromStorage],
	);

	/**
	 * Schedule a sync with server (debounced)
	 */
	const scheduleServerSync = useCallback(
		(pageNumber, syncCallback) => {
			// Save to localStorage immediately
			savePageToStorage(pageNumber);

			// Debounce server sync
			if (syncTimeoutRef.current) {
				clearTimeout(syncTimeoutRef.current);
			}

			syncTimeoutRef.current = setTimeout(() => {
				syncCallback(pageNumber);
			}, 1000); // 1 second debounce
		},
		[savePageToStorage],
	);

	/**
	 * Clean up old localStorage entries across all books
	 */
	const cleanupOldEntries = useCallback(() => {
		try {
			const now = Date.now();
			const maxAge = STORAGE_EXPIRY_DAYS * 24 * 60 * 60 * 1000;
			const keysToRemove = [];

			for (let i = 0; i < localStorage.length; i++) {
				const key = localStorage.key(i);
				if (key?.startsWith(STORAGE_KEY_PREFIX)) {
					try {
						const data = JSON.parse(localStorage.getItem(key));
						if (data && now - data.timestamp > maxAge) {
							keysToRemove.push(key);
						}
					} catch {
						// Invalid data, mark for removal
						keysToRemove.push(key);
					}
				}
			}

			for (const key of keysToRemove) {
				localStorage.removeItem(key);
			}

			if (keysToRemove.length > 0) {
				console.log(`Cleaned up ${keysToRemove.length} old book page entries`);
			}
		} catch (error) {
			console.warn("Failed to cleanup old localStorage entries:", error);
		}
	}, []);

	/**
	 * Cleanup on mount
	 */
	useEffect(() => {
		cleanupOldEntries();
	}, [cleanupOldEntries]);

	/**
	 * Cleanup sync timeout on unmount
	 */
	useEffect(() => {
		return () => {
			if (syncTimeoutRef.current) {
				clearTimeout(syncTimeoutRef.current);
			}
		};
	}, []);

	return {
		getInitialPage,
		scheduleServerSync,
		savePageToStorage,
		getLastPageFromStorage,
	};
};
