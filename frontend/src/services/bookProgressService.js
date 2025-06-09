/**
 * Service for calculating and managing book progress
 * Handles both page-based progress and table-of-contents completion
 */

/**
 * Calculate progress for a book including table of contents completion
 * @param {Object} book - Book object with tableOfContents
 * @returns {Object} Progress information
 */
export function calculateBookProgress(book) {
	if (!book) return { percentage: 0, completedSections: 0, totalSections: 0 };

	// Get saved progress from localStorage
	const tocProgressKey = `bookTocProgress_${book.id}`;
	const savedTocProgress = localStorage.getItem(tocProgressKey);
	const completedSectionIds = new Set();

	if (savedTocProgress) {
		try {
			const savedIds = JSON.parse(savedTocProgress);
			for (const id of savedIds) {
				completedSectionIds.add(id);
			}
		} catch (e) {
			console.error("Failed to parse saved ToC progress:", e);
		}
	}

	// Count total sections and completed sections using SAME LOGIC as BookSidebar
	const countAllSections = (chapters) => {
		let count = 0;
		for (const ch of chapters) {
			if (ch.children && ch.children.length > 0) {
				count += ch.children.length;
			} else {
				count += 1;
			}
		}
		return count;
	};

	// Count completed sections with same logic
	const countCompletedSections = (chapters) => {
		let count = 0;
		for (const ch of chapters) {
			if (ch.children && ch.children.length > 0) {
				// Count completed children
				for (const section of ch.children) {
					if (completedSectionIds.has(section.id)) {
						count++;
					}
				}
			} else {
				// Chapter is a section itself
				if (completedSectionIds.has(ch.id)) {
					count++;
				}
			}
		}
		return count;
	};

	let totalSections = 0;
	let completedSections = 0;

	if (book.tableOfContents && book.tableOfContents.length > 0) {
		totalSections = countAllSections(book.tableOfContents);
		completedSections = countCompletedSections(book.tableOfContents);
	}

	// If no table of contents, return 0 progress (don't use page-based)
	if (totalSections === 0) {
		return {
			percentage: 0,
			completedSections: 0,
			totalSections: 0,
			type: "section-based",
		};
	}

	// Calculate percentage
	const percentage =
		totalSections > 0
			? Math.round((completedSections / totalSections) * 100)
			: 0;

	const result = {
		percentage,
		completedSections,
		totalSections,
		type: "section-based",
	};

	// Save the calculated stats for future use (only section-based)
	if (totalSections > 0) {
		saveBookProgressStats(book.id, totalSections, completedSections);
	}

	return result;
}

/**
 * Update book progress in localStorage
 * @param {string} bookId - Book ID
 * @param {string} sectionId - Section ID to toggle
 * @param {boolean} isCompleted - Whether section is completed
 */
export function updateBookProgress(bookId, sectionId, isCompleted) {
	const tocProgressKey = `bookTocProgress_${bookId}`;
	const savedTocProgress = localStorage.getItem(tocProgressKey);
	const completedSectionIds = new Set();

	if (savedTocProgress) {
		try {
			const savedIds = JSON.parse(savedTocProgress);
			for (const id of savedIds) {
				completedSectionIds.add(id);
			}
		} catch (e) {
			console.error("Failed to parse saved ToC progress:", e);
		}
	}

	if (isCompleted) {
		completedSectionIds.add(sectionId);
	} else {
		completedSectionIds.delete(sectionId);
	}

	// Filter out UUID-like strings (API chapter IDs) to only save ToC progress
	const tocProgress = Array.from(completedSectionIds).filter(
		(id) =>
			!id.match(
				/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i,
			),
	);

	localStorage.setItem(tocProgressKey, JSON.stringify(tocProgress));

	// Emit custom event for same-tab updates
	window.dispatchEvent(
		new CustomEvent("bookProgressUpdate", {
			detail: { bookId },
		}),
	);
}

/**
 * Get completed sections for a book
 * @param {string} bookId - Book ID
 * @returns {Set} Set of completed section IDs
 */
export function getCompletedSections(bookId) {
	const tocProgressKey = `bookTocProgress_${bookId}`;
	const savedTocProgress = localStorage.getItem(tocProgressKey);
	const completedSectionIds = new Set();

	if (savedTocProgress) {
		try {
			const savedIds = JSON.parse(savedTocProgress);
			for (const id of savedIds) {
				completedSectionIds.add(id);
			}
		} catch (e) {
			console.error("Failed to parse saved ToC progress:", e);
		}
	}

	return completedSectionIds;
}

/**
 * Get quick progress stats for a book (when tableOfContents not available)
 * This is used for the home page cards
 * @param {string} bookId - Book ID
 * @returns {Object} Progress stats
 */
export function getBookProgressStats(bookId) {
	// Get the saved stats
	const statsKey = `bookProgressStats_${bookId}`;
	const existingStats = localStorage.getItem(statsKey);

	if (existingStats) {
		try {
			const stats = JSON.parse(existingStats);
			// IMPORTANT: Only return section-based stats
			if (stats.type === "section-based") {
				return stats;
			}
			// If we have page-based stats, ignore them
			console.warn("Ignoring page-based stats for book:", bookId);
		} catch (e) {
			console.error("Failed to parse book stats:", e);
		}
	}

	// If no valid stats saved, return default
	const completedSections = getCompletedSections(bookId);
	return {
		completedSections: completedSections.size,
		totalSections: 0,
		percentage: 0,
		type: "section-based",
	};
}

/**
 * Save book progress stats (called when we have full book data)
 * @param {string} bookId - Book ID
 * @param {number} totalSections - Total sections count from BookSidebar
 * @param {number} completedCount - Completed sections count from BookSidebar
 */
export function saveBookProgressStats(
	bookId,
	totalSections,
	completedCount = null,
) {
	const statsKey = `bookProgressStats_${bookId}`;

	// If completedCount not provided, count it ourselves
	const finalCompletedCount =
		completedCount !== null
			? completedCount
			: getCompletedSections(bookId).size;

	const percentage =
		totalSections > 0
			? Math.round((finalCompletedCount / totalSections) * 100)
			: 0;

	const stats = {
		totalSections,
		completedSections: finalCompletedCount,
		percentage,
		type: "section-based",
		lastUpdated: Date.now(),
	};

	localStorage.setItem(statsKey, JSON.stringify(stats));

	// Emit custom event for same-tab updates
	window.dispatchEvent(
		new CustomEvent("bookProgressUpdate", {
			detail: { bookId },
		}),
	);

	return stats;
}

/**
 * Clear cached stats for a book (useful for debugging)
 * @param {string} bookId - Book ID
 */
export function clearBookProgressStats(bookId) {
	const statsKey = `bookProgressStats_${bookId}`;
	localStorage.removeItem(statsKey);
}

// Debug: Clear any page-based stats on load
if (typeof window !== "undefined") {
	const allKeys = Object.keys(localStorage);
	for (const key of allKeys) {
		if (key.startsWith("bookProgressStats_")) {
			try {
				const stats = JSON.parse(localStorage.getItem(key));
				if (stats.type === "page-based") {
					console.log("Clearing page-based stats:", key);
					localStorage.removeItem(key);
				}
			} catch (e) {
				// Ignore parse errors
			}
		}
	}
}
