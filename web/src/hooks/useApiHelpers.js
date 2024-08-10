/**
 * Helper hooks for specific API operations in Phase 3
 */

import { useApi } from "./useApi"

/**
 * Hook for node operations
 * @param {string} nodeId - The node ID
 */
export function useNodeApi(nodeId = null) {
	const getNode = useApi("/nodes/{nodeId}")
	const updateNode = useApi("/nodes/{nodeId}", { method: "PATCH" })
	const updateStatus = useApi("/nodes/{nodeId}/status", { method: "PUT" })

	return {
		// Get node data
		async fetchNode() {
			if (!nodeId) throw new Error("Node ID required")
			return await getNode.execute(null, { pathParams: { nodeId } })
		},

		// Update node
		async updateNode(data) {
			if (!nodeId) throw new Error("Node ID required")
			return await updateNode.execute(data, { pathParams: { nodeId } })
		},

		// Update node status
		async updateStatus(status) {
			if (!nodeId) throw new Error("Node ID required")
			return await updateStatus.execute({ status }, { pathParams: { nodeId } })
		},

		// Loading states
		isLoading: getNode.isLoading || updateNode.isLoading || updateStatus.isLoading,
		error: getNode.error || updateNode.error || updateStatus.error,
	}
}

/**
 * Hook for course modules operations
 * @param {string} courseId - The course ID
 */
export function useRoadmapNodesApi(courseId = null) {
	const getCourseModules = useApi("/courses/{courseId}/modules")

	return {
		// Get all modules for a course
		async fetchNodes() {
			if (!courseId) throw new Error("Course ID required")
			return await getCourseModules.execute(null, { pathParams: { courseId } })
		},

		// Loading states
		isLoading: getCourseModules.isLoading,
		error: getCourseModules.error,
		data: getCourseModules.data,
	}
}

/**
 * Hook for book chapter operations
 * @param {string} bookId - The book ID
 */
export function useBookChaptersApi(bookId = null) {
	const getChapters = useApi("/books/{bookId}/chapters")
	const getChapter = useApi("/books/{bookId}/chapters/{chapterId}")
	const updateChapterStatus = useApi("/books/{bookId}/chapters/{chapterId}/status", { method: "PUT" })
	const extractChapters = useApi("/books/{bookId}/extract-chapters", {
		method: "POST",
	})

	return {
		// Get all chapters for a book
		async fetchChapters() {
			if (!bookId) throw new Error("Book ID required")
			return await getChapters.execute(null, { pathParams: { bookId } })
		},

		// Get a specific chapter
		async fetchChapter(chapterId) {
			if (!bookId || !chapterId) throw new Error("Book ID and Chapter ID required")
			return await getChapter.execute(null, {
				pathParams: { bookId, chapterId },
			})
		},

		// Update chapter status
		async updateChapterStatus(chapterId, status) {
			if (!bookId || !chapterId) throw new Error("Book ID and Chapter ID required")
			return await updateChapterStatus.execute({ status }, { pathParams: { bookId, chapterId } })
		},

		// Extract chapters from book
		async extractChapters() {
			if (!bookId) throw new Error("Book ID required")
			return await extractChapters.execute(null, { pathParams: { bookId } })
		},

		// Loading states
		isLoading:
			getChapters.isLoading || getChapter.isLoading || updateChapterStatus.isLoading || extractChapters.isLoading,
		error: getChapters.error || getChapter.error || updateChapterStatus.error || extractChapters.error,
		data: getChapters.data,
	}
}

/**
 * Hook for video chapter operations
 * @param {string} videoId - The video ID
 */
export function useVideoChaptersApi(videoId = null) {
	const getChapters = useApi("/videos/{videoId}/chapters")
	const getChapter = useApi("/videos/{videoId}/chapters/{chapterId}")
	const updateChapterStatus = useApi("/videos/{videoId}/chapters/{chapterId}/status", { method: "PUT" })
	const extractChapters = useApi("/videos/{videoId}/extract-chapters", {
		method: "POST",
	})

	return {
		// Get all chapters for a video
		async fetchChapters() {
			if (!videoId) throw new Error("Video ID required")
			return await getChapters.execute(null, { pathParams: { videoId } })
		},

		// Get a specific chapter
		async fetchChapter(chapterId) {
			if (!videoId || !chapterId) throw new Error("Video ID and Chapter ID required")
			return await getChapter.execute(null, {
				pathParams: { videoId, chapterId },
			})
		},

		// Update chapter status
		async updateChapterStatus(chapterId, status) {
			if (!videoId || !chapterId) throw new Error("Video ID and Chapter ID required")
			return await updateChapterStatus.execute({ status }, { pathParams: { videoId, chapterId } })
		},

		// Extract chapters from video
		async extractChapters() {
			if (!videoId) throw new Error("Video ID required")
			return await extractChapters.execute(null, { pathParams: { videoId } })
		},

		// Loading states
		isLoading:
			getChapters.isLoading || getChapter.isLoading || updateChapterStatus.isLoading || extractChapters.isLoading,
		error: getChapters.error || getChapter.error || updateChapterStatus.error || extractChapters.error,
		data: getChapters.data,
	}
}

/**
 * Hook for course operations (updated for unified course API)
 * @param {string} courseId - The course ID
 */
export function useCourseApi(courseId = null) {
	const getCourses = useApi("/courses")
	const getCourse = useApi("/courses/{courseId}")
	const getModules = useApi("/courses/{courseId}/modules")
	const getModule = useApi("/courses/{courseId}/modules/{moduleId}")
	const getLessons = useApi("/courses/{courseId}/modules/{moduleId}/lessons")
	const getLesson = useApi("/courses/{courseId}/modules/{moduleId}/lessons/{lessonId}")
	const getCourseProgress = useApi("/courses/{courseId}/progress")

	return {
		// Get all courses
		async fetchCourses(options = {}) {
			const { page = 1, perPage = 20, search } = options
			const queryParams = { page, per_page: perPage }
			if (search) queryParams.search = search
			return await getCourses.execute(null, { queryParams })
		},

		// Get course details
		async fetchCourse() {
			if (!courseId) throw new Error("Course ID required")
			return await getCourse.execute(null, { pathParams: { courseId } })
		},

		// Get course modules (replaces curriculum)
		async fetchModules() {
			if (!courseId) throw new Error("Course ID required")
			return await getModules.execute(null, { pathParams: { courseId } })
		},

		// Get specific module
		async fetchModule(moduleId) {
			if (!courseId || !moduleId) throw new Error("Course ID and Module ID required")
			return await getModule.execute(null, {
				pathParams: { courseId, moduleId },
			})
		},

		// Get lessons for a module
		async fetchLessons(moduleId) {
			if (!courseId || !moduleId) throw new Error("Course ID and Module ID required")
			return await getLessons.execute(null, {
				pathParams: { courseId, moduleId },
			})
		},

		// Get specific lesson
		async fetchLesson(moduleId, lessonId, options = {}) {
			if (!courseId || !moduleId || !lessonId) {
				throw new Error("Course ID, Module ID, and Lesson ID required")
			}
			const queryParams = {}
			if (options.generate) queryParams.generate = true
			return await getLesson.execute(null, {
				pathParams: { courseId, moduleId, lessonId },
				queryParams,
			})
		},

		// Get course progress
		async fetchCourseProgress() {
			if (!courseId) throw new Error("Course ID required")
			return await getCourseProgress.execute(null, {
				pathParams: { courseId },
			})
		},

		// Loading states
		isLoading:
			getCourses.isLoading ||
			getCourse.isLoading ||
			getModules.isLoading ||
			getModule.isLoading ||
			getLessons.isLoading ||
			getLesson.isLoading ||
			getCourseProgress.isLoading,
		error:
			getCourses.error ||
			getCourse.error ||
			getModules.error ||
			getModule.error ||
			getLessons.error ||
			getLesson.error ||
			getCourseProgress.error,
	}
}
