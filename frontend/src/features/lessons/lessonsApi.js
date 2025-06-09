// Use import.meta.env for Vite-based applications
const BASE = import.meta.env.VITE_API_BASE || "http://localhost:8080/api/v1";

/**
 * Generate a new lesson via API
 * @param {Object} request - The lesson generation request
 * @returns {Promise<Object>} The generated lesson
 */
export async function generateLesson(request) {
	// The correct endpoint is /nodes/{node_id}/lessons
	const nodeId = request.courseId;
	const res = await fetch(`${BASE}/nodes/${nodeId}/lessons`, {
		method: "POST",
		headers: { "Content-Type": "application/json" },
	});
	if (!res.ok) throw new Error(`Error ${res.status}`);
	return res.json();
}

/**
 * Fetch lessons for a specific node
 * @param {string} nodeId - The ID of the node
 * @returns {Promise<Array>} Array of lessons for the node
 */
export async function fetchLessonsByNodeId(nodeId) {
	const res = await fetch(`${BASE}/nodes/${nodeId}/lessons`);
	if (!res.ok) throw new Error(`Error ${res.status}`);
	return res.json();
}

/**
 * Fetch a specific lesson by ID
 * @param {string} lessonId - The ID of the lesson
 * @returns {Promise<Object>} The lesson data
 */
export async function fetchLessonById(lessonId) {
	const res = await fetch(`${BASE}/lessons/${lessonId}`);
	if (!res.ok) throw new Error(`Error ${res.status}`);
	return res.json();
}
