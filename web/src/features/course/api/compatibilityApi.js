/**
 * Course Compatibility Layer
 *
 * This module provides compatibility functions to help migrate from the old
 * roadmap/lesson/node structure to the new unified course API while maintaining
 * backward compatibility during the transition.
 */

import { useCourseService } from "./courseApi"

/**
 * Maps legacy roadmap data to course format
 * @param {Object} roadmap - Legacy roadmap data
 * @returns {Object} Course data in new format
 */
export function mapRoadmapToCourse(roadmap) {
	if (!roadmap) return null

	return {
		id: roadmap.id,
		title: roadmap.title,
		description: roadmap.description || "",
		skillLevel: roadmap.skill_level || roadmap.skillLevel || "beginner",
		tagsJson: roadmap.tags_json || roadmap.tagsJson || "[]",
		archived: roadmap.archived || false,
		archivedAt: roadmap.archived_at || roadmap.archivedAt,
		ragEnabled: roadmap.rag_enabled || roadmap.ragEnabled || false,
		createdAt: roadmap.created_at || roadmap.createdAt,
		updatedAt: roadmap.updated_at || roadmap.updatedAt,
		modules: roadmap.nodes ? roadmap.nodes.map(mapNodeToModule) : [],
	}
}

/**
 * Maps legacy node data to module format
 * @param {Object} node - Legacy node data
 * @returns {Object} Module data in new format
 */
export function mapNodeToModule(node) {
	if (!node) return null

	return {
		id: node.id,
		courseId: node.roadmap_id || node.roadmapId || node.courseId,
		parentId: node.parent_id || node.parentId,
		labelId: node.label_id || node.labelId,
		title: node.title,
		description: node.description || "",
		content: node.content || "",
		order: node.order || 0,
		status: node.status || "not_started",
		completionPercentage: node.completion_percentage || node.completionPercentage || 0,
		createdAt: node.created_at || node.createdAt,
		updatedAt: node.updated_at || node.updatedAt,
	}
}

/**
 * Maps course data back to legacy roadmap format
 * @param {Object} course - Course data in new format
 * @returns {Object} Legacy roadmap data
 */
export function mapCourseToRoadmap(course) {
	if (!course) return null

	return {
		id: course.id,
		title: course.title,
		description: course.description,
		skill_level: course.skillLevel,
		tags_json: course.tagsJson,
		archived: course.archived,
		archived_at: course.archivedAt,
		rag_enabled: course.ragEnabled,
		created_at: course.createdAt,
		updated_at: course.updatedAt,
		nodes: course.modules ? course.modules.map(mapModuleToNode) : [],
	}
}

/**
 * Maps module data back to legacy node format
 * @param {Object} module - Module data in new format
 * @returns {Object} Legacy node data
 */
export function mapModuleToNode(module) {
	if (!module) return null

	return {
		id: module.id,
		roadmap_id: module.courseId,
		parent_id: module.parentId,
		label_id: module.labelId,
		title: module.title,
		description: module.description,
		content: module.content,
		order: module.order,
		status: module.status,
		completion_percentage: module.completionPercentage,
		created_at: module.createdAt,
		updated_at: module.updatedAt,
	}
}

/**
 * Compatibility hook that provides both old and new API methods
 * This allows components to gradually migrate to the new API
 * @param {string} id - The course/roadmap ID
 */
export function useRoadmapCourseCompatibility(id = null) {
	const courseService = useCourseService(id)

	return {
		// ========== NEW API METHODS ==========
		course: courseService,

		// ========== LEGACY API WRAPPERS ==========

		/**
		 * Fetch roadmap (returns data in legacy format)
		 */
		async fetchRoadmap() {
			const course = await courseService.fetchCourse()
			return mapCourseToRoadmap(course)
		},

		/**
		 * Fetch roadmap nodes (returns modules in legacy format)
		 */
		async fetchRoadmapNodes() {
			const modules = await courseService.fetchModules()
			return modules ? modules.map(mapModuleToNode) : []
		},

		/**
		 * Update node status (maps to module update)
		 * @param {string} nodeId - The node/module ID
		 * @param {string} status - The new status
		 */
		async updateNodeStatus(nodeId, status) {
			// For now, we'll use the module update API
			// In the future, this might need more sophisticated mapping
			return await courseService.updateModule(nodeId, { status })
		},

		/**
		 * Fetch lesson for a node (maps to new lesson structure)
		 * @param {string} nodeId - The node/module ID
		 * @param {string} lessonId - The lesson ID (optional, for compatibility)
		 */
		async fetchNodeLesson(nodeId, lessonId = null) {
			if (lessonId) {
				// If we have a specific lesson ID, fetch it directly
				return await courseService.fetchLesson(nodeId, lessonId)
			}
			// If no lesson ID, fetch all lessons for the module and return the first one
			const lessons = await courseService.fetchLessons(nodeId)
			return lessons && lessons.length > 0 ? lessons[0] : null
		},

		// ========== UTILITY METHODS ==========

		/**
		 * Convert legacy data to new format
		 * @param {Object} legacyData - Data in old format
		 * @param {'roadmap'|'node'} type - Type of data being converted
		 */
		convertToNewFormat(legacyData, type) {
			switch (type) {
				case "roadmap":
					return mapRoadmapToCourse(legacyData)
				case "node":
					return mapNodeToModule(legacyData)
				default:
					return legacyData
			}
		},

		/**
		 * Convert new data to legacy format
		 * @param {Object} newData - Data in new format
		 * @param {'course'|'module'} type - Type of data being converted
		 */
		convertToLegacyFormat(newData, type) {
			switch (type) {
				case "course":
					return mapCourseToRoadmap(newData)
				case "module":
					return mapModuleToNode(newData)
				default:
					return newData
			}
		},

		// ========== COMBINED LOADING STATE ==========

		get isLoading() {
			return courseService.isLoading
		},

		get error() {
			return courseService.error
		},
	}
}

/**
 * Helper function to determine if we should use the new or legacy API
 * This can be controlled by environment variables or feature flags
 */
export function shouldUseNewCourseAPI() {
	// For now, always use new API. In the future, this could be:
	// - Controlled by environment variable
	// - Controlled by feature flag
	// - Controlled by user preference
	return true
}

/**
 * Smart API hook that automatically chooses between legacy and new APIs
 * @param {string} id - The course/roadmap ID
 */
export function useSmartCourseAPI(id = null) {
	const courseService = useCourseService(id)
	const roadmapCompatibilityService = useRoadmapCourseCompatibility(id)

	const useNewApi = shouldUseNewCourseAPI()

	if (useNewApi) {
		return courseService
	}
	return roadmapCompatibilityService
}

// Functions are already exported above individually
