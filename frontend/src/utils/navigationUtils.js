/**
 * Navigation Utilities for Course/Roadmap Migration
 *
 * This module provides utilities to handle navigation between legacy roadmap URLs
 * and new course URLs, ensuring smooth transition and backward compatibility.
 */

import { useLocation, useNavigate } from "react-router-dom";

/**
 * Generate course URL based on the simplified course structure
 * @param {string} courseId - Course ID
 * @param {string} [lessonId] - Optional lesson ID
 * @returns {string} Course URL
 */
export function generateCourseUrl(courseId, lessonId = null) {
	if (!courseId) return "/";

	let url = `/course/${courseId}`;

	if (lessonId) {
		url += `/lesson/${lessonId}`;
	}

	return url;
}

/**
 * Generate legacy roadmap URL (for backward compatibility)
 * @param {string} roadmapId - Roadmap ID
 * @returns {string} Roadmap URL
 */
export function generateRoadmapUrl(roadmapId) {
	if (!roadmapId) return "/";
	return `/roadmap/${roadmapId}`;
}

/**
 * Generate preview URL for courses
 * @param {string} courseId - Course ID
 * @param {boolean} [useLegacyFormat=false] - Whether to use legacy roadmap format
 * @returns {string} Preview URL
 */
export function generatePreviewUrl(courseId, useLegacyFormat = false) {
	if (!courseId) return "/";

	if (useLegacyFormat) {
		return `/roadmap/preview/${courseId}`;
	}

	return `/course/preview/${courseId}`;
}

/**
 * Convert legacy roadmap URL to new course URL
 * @param {string} roadmapUrl - Legacy roadmap URL
 * @returns {string} Equivalent course URL
 */
export function convertRoadmapToCourseUrl(roadmapUrl) {
	if (!roadmapUrl) return "/";

	// Handle preview URLs
	const previewMatch = roadmapUrl.match(/^\/roadmap\/preview\/(.+)$/);
	if (previewMatch) {
		return `/course/preview/${previewMatch[1]}`;
	}

	// Handle regular roadmap URLs
	const roadmapMatch = roadmapUrl.match(/^\/roadmap\/(.+)$/);
	if (roadmapMatch) {
		return `/course/${roadmapMatch[1]}`;
	}

	return roadmapUrl; // Return as-is if not a roadmap URL
}

/**
 * Convert course URL to legacy roadmap URL
 * @param {string} courseUrl - Course URL
 * @returns {string} Equivalent roadmap URL
 */
export function convertCourseToRoadmapUrl(courseUrl) {
	if (!courseUrl) return "/";

	// Handle preview URLs
	const previewMatch = courseUrl.match(/^\/course\/preview\/(.+)$/);
	if (previewMatch) {
		return `/roadmap/preview/${previewMatch[1]}`;
	}

	// Handle course URLs (strip module/lesson parts for roadmap compatibility)
	const courseMatch = courseUrl.match(/^\/course\/([^/]+)/);
	if (courseMatch) {
		return `/roadmap/${courseMatch[1]}`;
	}

	return courseUrl; // Return as-is if not a course URL
}

/**
 * Parse current URL to extract navigation parameters
 * @param {string} pathname - Current pathname
 * @returns {Object} Navigation parameters
 */
export function parseNavigationPath(pathname) {
	// Parse course URLs (simplified: /course/{courseId}/lesson/{lessonId})
	const courseMatch = pathname.match(
		/^\/course\/([^/]+)(?:\/lesson\/([^/]+))?$/,
	);
	if (courseMatch) {
		return {
			type: "course",
			courseId: courseMatch[1],
			moduleId: null, // No longer in URL
			lessonId: courseMatch[2] || null,
			isPreview: false,
		};
	}

	// Parse course preview URLs
	const coursePreviewMatch = pathname.match(/^\/course\/preview\/(.+)$/);
	if (coursePreviewMatch) {
		return {
			type: "course",
			courseId: coursePreviewMatch[1],
			moduleId: null,
			lessonId: null,
			isPreview: true,
		};
	}

	// Parse legacy roadmap URLs
	const roadmapMatch = pathname.match(/^\/roadmap\/(.+)$/);
	if (roadmapMatch) {
		return {
			type: "roadmap",
			roadmapId: roadmapMatch[1],
			courseId: roadmapMatch[1], // Treat roadmap ID as course ID for compatibility
			moduleId: null,
			lessonId: null,
			isPreview: false,
		};
	}

	// Parse legacy roadmap preview URLs
	const roadmapPreviewMatch = pathname.match(/^\/roadmap\/preview\/(.+)$/);
	if (roadmapPreviewMatch) {
		return {
			type: "roadmap",
			roadmapId: roadmapPreviewMatch[1],
			courseId: roadmapPreviewMatch[1],
			moduleId: null,
			lessonId: null,
			isPreview: true,
		};
	}

	// Default for non-course/roadmap URLs
	return {
		type: "other",
		courseId: null,
		moduleId: null,
		lessonId: null,
		isPreview: false,
	};
}

/**
 * Hook for course-aware navigation
 */
export function useCourseNavigation() {
	const navigate = useNavigate();
	const location = useLocation();

	const currentPath = parseNavigationPath(location.pathname);

	return {
		// Current navigation state
		current: currentPath,

		// Navigation functions
		goToCourse: (courseId) => {
			navigate(generateCourseUrl(courseId));
		},

		goToLesson: (courseId, lessonId) => {
			// Use roadmap format for now since that's what our current routing expects
			navigate(`/roadmap/${courseId}/lesson/${lessonId}`);
		},

		goToCoursePreview: (courseId) => {
			navigate(generatePreviewUrl(courseId));
		},

		// Legacy navigation (for backward compatibility)
		goToRoadmap: (roadmapId) => {
			navigate(generateRoadmapUrl(roadmapId));
		},

		goToRoadmapPreview: (roadmapId) => {
			navigate(generatePreviewUrl(roadmapId, true));
		},

		// Smart navigation that uses current format preference
		goToSmartCourse: (courseId, lessonId = null) => {
			// If currently on a legacy roadmap URL and no lesson, continue using legacy format
			if (currentPath.type === "roadmap" && !lessonId) {
				navigate(generateRoadmapUrl(courseId));
			} else {
				navigate(generateCourseUrl(courseId, lessonId));
			}
		},

		// Utility functions
		isOnCourse: (courseId) => {
			return currentPath.courseId === courseId;
		},

		isOnLesson: (courseId, lessonId) => {
			return (
				currentPath.courseId === courseId && currentPath.lessonId === lessonId
			);
		},
	};
}

/**
 * Hook for generating breadcrumb navigation
 */
export function useBreadcrumbNavigation() {
	const location = useLocation();
	const navigate = useNavigate();

	const currentPath = parseNavigationPath(location.pathname);

	const generateBreadcrumbs = (
		courseData,
		_moduleData = null,
		lessonData = null,
	) => {
		const breadcrumbs = [
			{
				label: "Home",
				path: "/",
				isActive: false,
			},
		];

		if (courseData) {
			breadcrumbs.push({
				label: courseData.title || "Course",
				path: generateCourseUrl(courseData.id),
				isActive: !currentPath.moduleId && !currentPath.lessonId,
			});
		}

		if (lessonData && currentPath.lessonId) {
			breadcrumbs.push({
				label: lessonData.title || lessonData.slug || "Lesson",
				path: generateCourseUrl(currentPath.courseId, lessonData.id),
				isActive: true,
			});
		}

		return breadcrumbs;
	};

	return {
		current: currentPath,
		generateBreadcrumbs,
		navigateTo: (path) => navigate(path),
	};
}

/**
 * Get the appropriate URL for a content item based on its type
 * @param {Object} item - Content item (course, book, video, etc.)
 * @param {string} type - Content type ('course', 'roadmap', 'book', 'video')
 * @returns {string} URL for the content item
 */
export function getContentUrl(item, type) {
	if (!item || !item.id) return "/";

	switch (type) {
		case "course":
			return generateCourseUrl(item.id);
		case "roadmap":
			return generateRoadmapUrl(item.id);
		case "book":
			return `/books/${item.id}`;
		case "video":
			return `/videos/${item.id}`;
		default:
			return "/";
	}
}

/**
 * Check if the current path matches a given pattern
 * @param {string} pattern - URL pattern to match
 * @param {string} [pathname] - Optional pathname (uses current if not provided)
 * @returns {boolean} Whether the path matches
 */
export function matchesPath(pattern, pathname = window.location.pathname) {
	const regex = new RegExp(pattern.replace(/:\w+/g, "[^/]+"));
	return regex.test(pathname);
}

// Export utility functions for direct use
export {
	generateCourseUrl as courseUrl,
	generateRoadmapUrl as roadmapUrl,
	generatePreviewUrl as previewUrl,
	parseNavigationPath as parsePath,
	convertRoadmapToCourseUrl as roadmapToCourse,
	convertCourseToRoadmapUrl as courseToRoadmap,
	getContentUrl as contentUrl,
};
