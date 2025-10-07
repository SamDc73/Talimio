import { api } from "@/lib/apiClient.js"

export async function executeCode({ code, language, lessonId, courseId }) {
	if (!code || !language) {
		throw new Error("code and language are required")
	}
	const payload = {
		code,
		language,
		...(lessonId ? { lesson_id: lessonId } : {}),
		...(courseId ? { course_id: courseId } : {}),
	}
	return api.post("/courses/code/execute", payload)
}

// Removed getSuggestedLanguages - backend handles all language support via fast-path + AI fallback
