/**
 * Enhanced Table of Contents Progress Service using Zustand store
 * Replaces localStorage-based bookProgressService with unified state management
 */

import useAppStore from "@/stores/useAppStore";

/**
 * Initialize ToC progress for a book
 * @param {string} bookId - Book identifier
 * @param {object} book - Book object with tableOfContents
 */
export function initializeTocProgress(bookId, book) {
	const store = useAppStore.getState();
	store.initializeTocProgress(bookId, book);
}

/**
 * Update section completion status
 * @param {string} bookId - Book identifier
 * @param {string} sectionId - Section identifier
 * @param {boolean} isCompleted - Completion status
 */
export function updateSectionProgress(bookId, sectionId, isCompleted) {
	const store = useAppStore.getState();
	store.updateTocSectionProgress(bookId, sectionId, isCompleted);
}

/**
 * Batch update multiple sections
 * @param {string} bookId - Book identifier
 * @param {Array} updates - Array of {sectionId, isCompleted} objects
 * @param {boolean} skipSync - Whether to skip API sync (for migrations)
 */
export function batchUpdateSections(bookId, updates, skipSync = false) {
	const store = useAppStore.getState();
	store.batchUpdateTocProgress(bookId, updates, skipSync);
}

/**
 * Get completed sections for a book
 * @param {string} bookId - Book identifier
 * @returns {Set<string>} Set of completed section IDs
 */
export function getCompletedSections(bookId) {
	const store = useAppStore.getState();
	const tocProgress = store.books.tocProgress[bookId] || {};
	return new Set(
		Object.entries(tocProgress)
			.filter(([_, completed]) => completed)
			.map(([sectionId, _]) => sectionId),
	);
}

/**
 * Get progress statistics for a book
 * @param {string} bookId - Book identifier
 * @returns {object} Progress stats {totalSections, completedSections, percentage}
 */
export function getBookProgressStats(bookId) {
	const store = useAppStore.getState();
	return (
		store.books.progressStats[bookId] || {
			totalSections: 0,
			completedSections: 0,
			percentage: 0,
			type: "unknown",
		}
	);
}

/**
 * Calculate progress from table of contents structure
 * @param {string} bookId - Book identifier
 * @param {object} tableOfContents - ToC structure
 * @returns {object} Progress statistics
 */
export function calculateBookProgress(bookId, tableOfContents) {
	const store = useAppStore.getState();
	return store.calculateTocProgress(bookId, tableOfContents);
}

/**
 * Recalculate and cache progress stats
 * @param {string} bookId - Book identifier
 */
export function recalculateProgressStats(bookId) {
	const store = useAppStore.getState();
	return store.recalculateBookProgressStats(bookId);
}

/**
 * Check if a section is completed
 * @param {string} bookId - Book identifier
 * @param {string} sectionId - Section identifier
 * @returns {boolean} True if section is completed
 */
export function isSectionCompleted(bookId, sectionId) {
	const completedSections = getCompletedSections(bookId);
	return completedSections.has(sectionId);
}

/**
 * Toggle section completion status
 * @param {string} bookId - Book identifier
 * @param {string} sectionId - Section identifier
 * @returns {boolean} New completion status
 */
export function toggleSectionCompletion(bookId, sectionId) {
	const currentStatus = isSectionCompleted(bookId, sectionId);
	const newStatus = !currentStatus;
	updateSectionProgress(bookId, sectionId, newStatus);
	return newStatus;
}

/**
 * Get chapter progress (for chapters with children)
 * @param {string} bookId - Book identifier
 * @param {object} chapter - Chapter object with children
 * @returns {number} Progress percentage (0-100)
 */
export function getChapterProgress(bookId, chapter) {
	if (!chapter.children || chapter.children.length === 0) {
		// Chapter without children - check if it's completed
		return isSectionCompleted(bookId, chapter.id) ? 100 : 0;
	}

	const completedSections = getCompletedSections(bookId);
	const completedCount = chapter.children.filter((section) =>
		completedSections.has(section.id),
	).length;

	return Math.round((completedCount / chapter.children.length) * 100);
}

/**
 * Mark chapter as in-progress when entering page range
 * @param {string} bookId - Book identifier
 * @param {number} currentPage - Current page number
 * @param {object} tableOfContents - ToC structure
 */
export function markChapterInProgress(bookId, currentPage, tableOfContents) {
	if (!tableOfContents) return;

	const findChapterForPage = (chapters) => {
		for (const chapter of chapters) {
			if (
				chapter.level === 0 &&
				chapter.startPage <= currentPage &&
				chapter.endPage >= currentPage &&
				!isSectionCompleted(bookId, chapter.id)
			) {
				return chapter.id;
			}
			if (chapter.children) {
				const found = findChapterForPage(chapter.children);
				if (found) return found;
			}
		}
		return null;
	};

	const chapters = Array.isArray(tableOfContents)
		? tableOfContents
		: [tableOfContents];
	const chapterId = findChapterForPage(chapters);

	if (chapterId) {
		// Mark as in-progress (we'll use true for now, can be enhanced to track states)
		updateSectionProgress(bookId, chapterId, true);
	}
}

/**
 * Get all book progress data for export/backup
 * @param {string} bookId - Book identifier
 * @returns {object} Complete progress data
 */
export function exportBookProgress(bookId) {
	const store = useAppStore.getState();
	return {
		bookId,
		tocProgress: store.books.tocProgress[bookId] || {},
		progressStats: store.books.progressStats[bookId] || {
			totalSections: 0,
			completedSections: 0,
			percentage: 0,
			type: "unknown",
		},
		bookProgress: store.getBookProgress(bookId),
		exportedAt: Date.now(),
	};
}

/**
 * Import progress data (for migration or restore)
 * @param {string} bookId - Book identifier
 * @param {object} progressData - Progress data to import
 */
export function importBookProgress(bookId, progressData) {
	const store = useAppStore.getState();

	if (progressData.tocProgress) {
		const updates = Object.entries(progressData.tocProgress).map(
			([sectionId, isCompleted]) => ({ sectionId, isCompleted }),
		);
		store.batchUpdateTocProgress(bookId, updates);
	}

	if (progressData.bookProgress) {
		store.updateBookProgress(bookId, progressData.bookProgress);
	}
}

/**
 * Migrate from old localStorage-based progress
 * @param {string} bookId - Book identifier
 */
export function migrateFromLocalStorage(bookId) {
	try {
		// Migrate from old bookTocProgress format
		const oldProgressKey = `bookTocProgress_${bookId}`;
		const oldProgress = localStorage.getItem(oldProgressKey);

		if (oldProgress) {
			const completedSections = JSON.parse(oldProgress);
			const updates = completedSections.map((sectionId) => ({
				sectionId,
				isCompleted: true,
			}));

			batchUpdateSections(bookId, updates, true); // Skip sync during migration

			console.log(
				`✅ Migrated ToC progress for book ${bookId}: ${updates.length} sections`,
			);

			// Optionally remove old data
			// localStorage.removeItem(oldProgressKey);
		}

		// Migrate from old stats format
		const oldStatsKey = `bookProgressStats_${bookId}`;
		const oldStats = localStorage.getItem(oldStatsKey);

		if (oldStats) {
			console.log(
				`📊 Found old progress stats for book ${bookId}:`,
				JSON.parse(oldStats),
			);
			// Stats will be recalculated automatically

			// Optionally remove old data
			// localStorage.removeItem(oldStatsKey);
		}
	} catch (error) {
		console.error(`Failed to migrate ToC progress for book ${bookId}:`, error);
	}
}

/**
 * React hook for using ToC progress
 * @param {string} bookId - Book identifier
 * @returns {object} ToC progress utilities
 */
export function useTocProgress(bookId) {
	return {
		completedSections: getCompletedSections(bookId),
		progressStats: getBookProgressStats(bookId),
		updateSection: (sectionId, isCompleted) =>
			updateSectionProgress(bookId, sectionId, isCompleted),
		toggleSection: (sectionId) => toggleSectionCompletion(bookId, sectionId),
		isCompleted: (sectionId) => isSectionCompleted(bookId, sectionId),
		getChapterProgress: (chapter) => getChapterProgress(bookId, chapter),
		recalculateStats: () => recalculateProgressStats(bookId),
	};
}
