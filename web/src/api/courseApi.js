/**
 * Course Service - Unified API client for the new course endpoints
 *
 * This service provides access to the unified course API that replaces
 * the separated course/lesson endpoints with a cohesive structure:
 *
 * Courses → Modules → Lessons
 */

import { useApi } from "@/hooks/use-api"
import { api } from "@/lib/apiClient"

function requireCourseId(courseId) {
	if (!courseId) {
		throw new Error("Course ID required")
	}

	return encodeURIComponent(String(courseId))
}

function buildCoursePath(courseId, suffix = "") {
	return `/courses/${requireCourseId(courseId)}${suffix}`
}

export async function fetchCourseById(courseId, signal) {
	return api.get(buildCoursePath(courseId), { signal })
}

export async function fetchConceptFrontierByCourseId(courseId, signal) {
	return api.get(buildCoursePath(courseId, "/concepts"), { signal })
}

/**
 * Hook for course operations
 * @param {string} courseId - The course ID
 */
export function useCourseService(courseId = null) {
	// Course endpoints
	const createCourse = useApi("/courses/", { method: "POST" })
	const getCourses = useApi("/courses/")
	const getCourse = useApi("/courses/{courseId}")
	const updateCourse = useApi("/courses/{courseId}", { method: "PATCH" })
	const selfAssessmentQuestions = useApi("/courses/self-assessment/questions", { method: "POST" })
	const getConceptFrontier = useApi("/courses/{courseId}/concepts")
	const createQuestionSetEndpoint = useApi("/courses/{courseId}/question-sets", { method: "POST" })
	const submitAttemptEndpoint = useApi("/courses/{courseId}/attempts", { method: "POST" })
	const submitConceptReviewEndpoint = useApi("/courses/{courseId}/lessons/{lessonId}/concept-reviews", {
		method: "POST",
	})
	const getConceptNextReview = useApi("/courses/{courseId}/concepts/{conceptId}/next-review")

	// Lesson endpoints
	const getLessons = useApi("/courses/{courseId}/lessons")
	const getLesson = useApi("/courses/{courseId}/lessons/{lessonId}")
	const generateLesson = useApi("/courses/{courseId}/lessons", {
		method: "POST",
	})
	const regenerateLesson = useApi("/courses/{courseId}/lessons/{lessonId}/regenerate", { method: "POST" })
	const updateLesson = useApi("/courses/{courseId}/lessons/{lessonId}", {
		method: "PATCH",
	})

	return {
		// ========== COURSE OPERATIONS ==========

		/**
		 * Create a new course
		 * @param {Object} courseData - Course creation data
		 * @param {string} courseData.prompt - AI prompt for course generation
		 * @param {boolean} courseData.adaptive_enabled - Whether adaptive mode is enabled
		 * @param {File[]} [courseData.files] - Optional attachments (pdf/epub/images)
		 */
		async createCourse(courseData) {
			const formData = new FormData()
			formData.append("prompt", courseData?.prompt ?? "")
			formData.append("adaptive_enabled", String(Boolean(courseData?.adaptive_enabled)))

			const files = Array.isArray(courseData?.files) ? courseData.files : []
			for (const file of files) {
				formData.append("files", file)
			}

			return await createCourse.execute(formData)
		},

		async fetchSelfAssessmentQuestions(payload) {
			return await selfAssessmentQuestions.execute(payload)
		},

		/**
		 * Fetch adaptive concept frontier and review queue
		 */
		async fetchConceptFrontier() {
			return await fetchConceptFrontierByCourseId(courseId)
		},

		async fetchQuestionSet(payload) {
			if (!courseId) {
				throw new Error("Course ID required")
			}
			if (!payload?.conceptId) {
				throw new Error("conceptId is required")
			}
			if (typeof payload?.count !== "number" || Number.isNaN(payload.count)) {
				throw new TypeError("count must be a number")
			}

			return await createQuestionSetEndpoint.execute(
				{
					conceptId: payload.conceptId,
					count: payload.count,
					practiceContext: payload.practiceContext ?? "drill",
					lessonId: payload.lessonId ?? null,
				},
				{ pathParams: { courseId } }
			)
		},

		async submitAttempt(payload) {
			if (!courseId) {
				throw new Error("Course ID required")
			}
			if (!payload?.attemptId || !payload?.questionId || !payload?.answer?.kind) {
				throw new Error("attemptId, questionId, and answer.kind are required")
			}
			return await submitAttemptEndpoint.execute(payload, { pathParams: { courseId } })
		},

		/**
		 * Create a course from uploaded document
		 * @param {FormData} formData - Form data containing file and metadata
		 * @returns {Promise<Object>} The created course data
		 */
		async createCourseFromDocument(formData) {
			return api.post("/courses/upload", formData)
		},

		/**
		 * Extract metadata from a document
		 * @param {File} file - The document file to analyze
		 * @returns {Promise<Object>} Extracted metadata
		 */
		async extractDocumentMetadata(file) {
			const formData = new FormData()
			formData.append("file", file)

			return api.post("/courses/extract-metadata", formData)
		},

		/**
		 * Get all courses with pagination and search
		 * @param {Object} options - Query options
		 * @param {number} options.page - Page number (default: 1)
		 * @param {number} options.perPage - Items per page (default: 20)
		 * @param {string} options.search - Search query
		 */
		async fetchCourses(options = {}) {
			const { page = 1, perPage = 20, search } = options
			const queryParams = { page, per_page: perPage }
			if (search) queryParams.search = search

			return await getCourses.execute(null, { queryParams })
		},

		/**
		 * Get a specific course by ID
		 */
		async fetchCourse() {
			return await fetchCourseById(courseId)
		},

		/**
		 * Update a course
		 * @param {Object} updateData - Course update data
		 */
		async updateCourse(updateData) {
			if (!courseId) throw new Error("Course ID required")
			return await updateCourse.execute(updateData, {
				pathParams: { courseId },
			})
		},

		// ========== LESSON OPERATIONS ==========

		/**
		 * Get all lessons for a course
		 */
		async fetchLessons() {
			if (!courseId) throw new Error("Course ID required")
			return await getLessons.execute(null, { pathParams: { courseId } })
		},

		/**
		 * Get a specific lesson
		 * @param {string} lessonId - Lesson ID
		 * @param {Object} options - Options
		 * @param {boolean} options.generate - Auto-generate if lesson doesn't exist
		 */
		async fetchLesson(lessonId, options = {}) {
			if (!courseId || !lessonId) {
				throw new Error("Course ID and Lesson ID required")
			}

			const queryParams = {}
			if (options.generate) queryParams.generate = true
			if (options.versionId) queryParams.versionId = options.versionId
			if (options.adaptiveFlow) queryParams.adaptiveFlow = true

			return await getLesson.execute(null, {
				pathParams: { courseId, lessonId },
				queryParams,
			})
		},

		/**
		 * Generate a new lesson for a course
		 * @param {Object} lessonData - Lesson creation data
		 */
		async generateLesson(lessonData) {
			if (!courseId) throw new Error("Course ID required")
			return await generateLesson.execute(lessonData, {
				pathParams: { courseId },
			})
		},

		/**
		 * Regenerate an existing lesson
		 * @param {string} lessonId - Lesson ID
		 */
		async regenerateLesson(lessonId, payload = {}) {
			if (!courseId || !lessonId) {
				throw new Error("Course ID and Lesson ID required")
			}

			const critiqueText = payload?.critiqueText?.trim()
			if (!critiqueText) {
				throw new Error("critiqueText is required")
			}

			return await regenerateLesson.execute(
				{
					critiqueText,
					applyAcrossCourse: Boolean(payload?.applyAcrossCourse),
				},
				{
					pathParams: { courseId, lessonId },
				}
			)
		},

		/**
		 * Update a lesson
		 * @param {string} lessonId - Lesson ID
		 * @param {Object} updateData - Lesson update data
		 */
		async updateLesson(lessonId, updateData) {
			if (!courseId || !lessonId) {
				throw new Error("Course ID and Lesson ID required")
			}
			return await updateLesson.execute(updateData, {
				pathParams: { courseId, lessonId },
			})
		},

		async submitConceptReview(lessonId, payload) {
			if (!courseId || !lessonId) {
				throw new Error("Course ID and Lesson ID required")
			}
			if (!payload?.conceptId) {
				throw new Error("conceptId is required")
			}
			return await submitConceptReviewEndpoint.execute(payload, { pathParams: { courseId, lessonId } })
		},

		/**
		 * Retrieve next review info for a concept
		 */
		async fetchConceptNextReview(conceptId) {
			if (!courseId || !conceptId) {
				throw new Error("Course ID and Concept ID required")
			}
			return await getConceptNextReview.execute(null, {
				pathParams: { courseId, conceptId },
			})
		},

		// ========== PROGRESS OPERATIONS ==========

		// ========== LOADING STATES AND ERRORS ==========

		/**
		 * Check if any operation is loading
		 */
		get isLoading() {
			return (
				createCourse.isLoading ||
				getCourses.isLoading ||
				getCourse.isLoading ||
				updateCourse.isLoading ||
				getConceptFrontier.isLoading ||
				createQuestionSetEndpoint.isLoading ||
				submitAttemptEndpoint.isLoading ||
				getLessons.isLoading ||
				getLesson.isLoading ||
				generateLesson.isLoading ||
				regenerateLesson.isLoading ||
				updateLesson.isLoading ||
				submitConceptReviewEndpoint.isLoading ||
				getConceptNextReview.isLoading
			)
		},

		/**
		 * Get any error that occurred
		 */
		get error() {
			return (
				createCourse.error ||
				getCourses.error ||
				getCourse.error ||
				updateCourse.error ||
				getConceptFrontier.error ||
				createQuestionSetEndpoint.error ||
				submitAttemptEndpoint.error ||
				getLessons.error ||
				getLesson.error ||
				generateLesson.error ||
				regenerateLesson.error ||
				updateLesson.error ||
				submitConceptReviewEndpoint.error ||
				getConceptNextReview.error
			)
		},
	}
}

/**
 * Convenience hook for global course operations (no specific courseId)
 */
export function useCourseGlobalService() {
	return useCourseService()
}
