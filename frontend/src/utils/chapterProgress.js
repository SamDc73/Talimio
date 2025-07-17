/**
 * Utility functions for chapter-based progress calculations
 */

/**
 * Calculate completion percentage based on completed chapters
 * @param {Array} chapters - Array of chapter objects
 * @param {Set|Object} completedChapters - Set of completed chapter IDs or object with chapter completion status
 * @returns {number} Completion percentage (0-100)
 */
export function calculateChapterProgress(chapters, completedChapters) {
	if (!chapters || chapters.length === 0) return 0;

	let completedCount = 0;

	// Handle both Set and Object formats
	if (completedChapters instanceof Set) {
		completedCount = chapters.filter((chapter) =>
			completedChapters.has(chapter.id || chapter.uuid),
		).length;
	} else if (typeof completedChapters === "object") {
		completedCount = chapters.filter(
			(chapter) => completedChapters[chapter.id || chapter.uuid] === true,
		).length;
	}

	return Math.round((completedCount / chapters.length) * 100);
}

/**
 * Get progress display text for chapters
 * @param {Array} chapters - Array of chapter objects
 * @param {Set|Object} completedChapters - Set of completed chapter IDs or object with chapter completion status
 * @returns {string} Progress display text like "3/10 chapters (30%)"
 */
export function getChapterProgressText(chapters, completedChapters) {
	if (!chapters || chapters.length === 0) return "0/0 chapters (0%)";

	let completedCount = 0;

	// Handle both Set and Object formats
	if (completedChapters instanceof Set) {
		completedCount = chapters.filter((chapter) =>
			completedChapters.has(chapter.id || chapter.uuid),
		).length;
	} else if (typeof completedChapters === "object") {
		completedCount = chapters.filter(
			(chapter) => completedChapters[chapter.id || chapter.uuid] === true,
		).length;
	}

	const percentage = calculateChapterProgress(chapters, completedChapters);
	return `${completedCount}/${chapters.length} chapters (${percentage}%)`;
}
