/**
 * Utilities for course data fetching
 * This module now only supports the unified course API
 */

const BASE_URL = import.meta.env.VITE_API_BASE || "/api/v1";

/**
 * Fetch course data using the course API
 *
 * @param {string} courseId - The course ID
 * @returns {Promise<object>} - Course data
 */
export async function fetchCourseData(courseId) {
	if (!courseId) {
		throw new Error("Course ID is required");
	}

	try {
		const courseResponse = await fetch(`${BASE_URL}/courses/${courseId}`);

		if (!courseResponse.ok) {
			throw new Error(`Course not found: ${courseId}`);
		}

		const courseData = await courseResponse.json();
		return courseData;
	} catch (error) {
		console.error("Error fetching course data:", error);
		throw error;
	}
}

/**
 * Get course data with structured modules
 *
 * @param {string} courseId - The course ID
 * @returns {Promise<{data: object, modules: array}>} - Complete course data with structured modules
 */
export async function getCourseWithModules(courseId) {
	const data = await fetchCourseData(courseId);

	// The API already returns modules with lessons nested inside them
	// No transformation needed - just return the modules directly
	const modules = data.modules || [];

	return {
		data,
		modules,
	};
}

/**
 * Check if a course exists
 *
 * @param {string} courseId - The course ID to check
 * @returns {Promise<boolean>} - True if course exists
 */
export async function courseExists(courseId) {
	try {
		await fetchCourseData(courseId);
		return true;
	} catch (_error) {
		return false;
	}
}

/**
 * Detect if an ID should be treated as course mode
 * This function tries to fetch course data and returns mode information
 *
 * @param {string} courseId - The ID to check
 * @returns {Promise<{isCourseMode: boolean}>} - Object indicating the detected mode
 */
export async function detectCourseMode(courseId) {
	try {
		await fetchCourseData(courseId);
		// If successful, it's a course
		return { isCourseMode: true };
	} catch (_error) {
		// If failed, assume it's a legacy roadmap
		return { isCourseMode: false };
	}
}
