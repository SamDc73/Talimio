/**
 * Course Service - Unified API client for the new course endpoints
 *
 * This service provides access to the unified course API that replaces
 * the separated course/lesson endpoints with a cohesive structure:
 *
 * Courses → Modules → Lessons
 */

import { api } from "@/lib/apiClient"
import { useApi } from "../../../hooks/use-api"

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
	const submitReviewsEndpoint = useApi("/courses/{courseId}/lessons/{lessonId}/reviews", { method: "POST" })
	const getConceptNextReview = useApi("/courses/{courseId}/concepts/{conceptId}/next-review")
	const gradeLessonAnswerEndpoint = useApi("/courses/{courseId}/lessons/{lessonId}/grade", { method: "POST" })

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
		 */
		async createCourse(courseData) {
			return await createCourse.execute(courseData)
		},

		async fetchSelfAssessmentQuestions(payload) {
			return await selfAssessmentQuestions.execute(payload)
		},

		/**
		 * Fetch adaptive concept frontier and review queue
		 */
		async fetchConceptFrontier() {
			if (!courseId) {
				throw new Error("Course ID required")
			}
			return await getConceptFrontier.execute(null, { pathParams: { courseId } })
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
			if (!courseId) throw new Error("Course ID required")
			return await getCourse.execute(null, { pathParams: { courseId } })
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
		async regenerateLesson(lessonId) {
			if (!courseId || !lessonId) {
				throw new Error("Course ID and Lesson ID required")
			}
			return await regenerateLesson.execute(null, {
				pathParams: { courseId, lessonId },
			})
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

		/**
		 * Delete a lesson
		 * @param {string} lessonId - Lesson ID
		 */

		/**
		 * Submit adaptive lesson reviews
		 */
		async submitLessonReviews(lessonId, reviews) {
			if (!courseId || !lessonId) {
				throw new Error("Course ID and Lesson ID required")
			}
			if (!Array.isArray(reviews) || reviews.length === 0) {
				throw new Error("At least one review is required")
			}
			return await submitReviewsEndpoint.execute({ reviews }, { pathParams: { courseId, lessonId } })
		},

		/**
		 * Grade a lesson answer for a practice interaction
		 * @param {string} lessonId - Lesson ID
		 * @param {Object} payload - Grading payload
		 */
		async gradeLessonAnswer(lessonId, payload) {
			if (!courseId || !lessonId) {
				throw new Error("Course ID and Lesson ID required")
			}
			return await gradeLessonAnswerEndpoint.execute(payload, { pathParams: { courseId, lessonId } })
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
				getLessons.isLoading ||
				getLesson.isLoading ||
				generateLesson.isLoading ||
				regenerateLesson.isLoading ||
				updateLesson.isLoading ||
				submitReviewsEndpoint.isLoading ||
				getConceptNextReview.isLoading ||
				gradeLessonAnswerEndpoint.isLoading
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
				getLessons.error ||
				getLesson.error ||
				generateLesson.error ||
				regenerateLesson.error ||
				updateLesson.error ||
				submitReviewsEndpoint.error ||
				getConceptNextReview.error ||
				gradeLessonAnswerEndpoint.error
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
