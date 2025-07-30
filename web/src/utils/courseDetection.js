import { api } from "@/lib/api";

/**
 * Fetches course data with modules and lessons in a structured format
 * @param {string} courseId - The course ID to fetch
 * @returns {Promise<{modules: Array}>} Course data with structured modules
 */
export async function getCourseWithModules(courseId) {
	if (!courseId) {
		throw new Error("Course ID is required");
	}

	try {
		// Fetch the complete course data from the main course endpoint
		// This includes modules and lessons in the response
		const courseData = await api.get(`/api/v1/courses/${courseId}`);

		// The API returns modules with nested lessons already structured
		const modules = courseData.modules || [];

		return { modules };
	} catch (error) {
		console.error("Error fetching course with modules:", error);
		throw error;
	}
}
