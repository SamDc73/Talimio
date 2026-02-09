import { api } from "@/lib/apiClient"

export async function executeCode({ code, language, lessonId, courseId, files, entryFile, workspaceId }) {
	if (!code || !language) {
		throw new Error("code and language are required")
	}
	const payload = {
		code,
		language,
		...(lessonId ? { lesson_id: lessonId } : {}),
		...(courseId ? { course_id: courseId } : {}),
	}

	if (Array.isArray(files) && files.length > 0) {
		payload.files = files.map((file) => ({ path: file.path, content: file.content }))
		if (entryFile) {
			payload.entry_file = entryFile
		}
		if (workspaceId) {
			payload.workspace_id = workspaceId
		}
	}

	return api.post("/courses/code/execute", payload)
}

// Removed getSuggestedLanguages - backend handles all language support via fast-path + AI fallback
