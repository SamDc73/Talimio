/**
 * Progress Compatibility Layer
 *
 * This module provides compatibility between legacy (node-based) and new
 * (course/module/lesson-based) progress systems during the migration period.
 */

import { createContext, useContext, useEffect, useState } from "react";
import { useCourseProgressSafe } from "./useCourseProgress";
import { progressUtils } from "./useCourseProgress";
import { useProgressSafe } from "./useProgress";

const ProgressCompatibilityContext = createContext(null);

/**
 * Progress Compatibility Provider that can handle both systems
 *
 * @param {Object} props
 * @param {React.ReactNode} props.children - Child components
 * @param {string} props.courseId - Course ID (new system)
 * @param {string} props.roadmapId - Roadmap ID (legacy system)
 * @param {boolean} props.useNewProgress - Force use of new progress system
 * @param {boolean} props.useLegacyProgress - Force use of legacy progress system
 * @param {Object} props.mappings - Mappings between legacy and new IDs
 */
export function ProgressCompatibilityProvider({
	children,
	courseId,
	roadmapId,
	useNewProgress = false,
	useLegacyProgress = false,
	mappings = {},
}) {
	const [activeSystem, setActiveSystem] = useState("auto");
	const [migrationData, setMigrationData] = useState({});

	// Determine which system to use
	const shouldUseNewProgress =
		useNewProgress || (!useLegacyProgress && courseId);
	const shouldUseLegacyProgress =
		useLegacyProgress || (!useNewProgress && roadmapId && !courseId);

	// Get both progress systems (safely)
	const newProgress = useCourseProgressSafe();
	const legacyProgress = useProgressSafe();

	useEffect(() => {
		if (shouldUseNewProgress) {
			setActiveSystem("new");
		} else if (shouldUseLegacyProgress) {
			setActiveSystem("legacy");
		} else {
			setActiveSystem("none");
		}
	}, [shouldUseNewProgress, shouldUseLegacyProgress]);

	/**
	 * Unified progress interface that works with both systems
	 */
	const unifiedProgress = {
		// System identification
		activeSystem,
		isNewSystem: activeSystem === "new",
		isLegacySystem: activeSystem === "legacy",
		isActiveSystem: activeSystem !== "none",

		// Progress data (adapted to common format)
		courseProgress:
			activeSystem === "new"
				? newProgress.courseProgress
				: activeSystem === "legacy"
					? adaptLegacyProgressToCourse(legacyProgress.courseProgress)
					: getDefaultProgress(),

		// Loading and error states
		isLoading:
			activeSystem === "new"
				? newProgress.isLoading
				: activeSystem === "legacy"
					? legacyProgress.isLoading
					: false,

		error:
			activeSystem === "new"
				? newProgress.error
				: activeSystem === "legacy"
					? legacyProgress.error
					: null,

		// Lesson completion checking (unified interface)
		isLessonCompleted: (moduleId, lessonId) => {
			if (activeSystem === "new") {
				return newProgress.isLessonCompleted(moduleId, lessonId);
			}if (activeSystem === "legacy") {
				// Convert new format to legacy nodeId
				const nodeId = convertToLegacyNodeId(moduleId, lessonId, mappings);
				return legacyProgress.isLessonCompleted(nodeId);
			}
			return false;
		},

		// Lesson status getting (unified interface)
		getLessonStatus: (moduleId, lessonId) => {
			if (activeSystem === "new") {
				return newProgress.getLessonStatus(moduleId, lessonId);
			}if (activeSystem === "legacy") {
				const nodeId = convertToLegacyNodeId(moduleId, lessonId, mappings);
				const legacyStatus =
					legacyProgress.lessonStatuses[nodeId] || "not_started";
				return progressUtils.convertLegacyStatus(legacyStatus);
			}
			return "not_started";
		},

		// Lesson completion toggling (unified interface)
		toggleLessonCompletion: async (moduleId, lessonId) => {
			if (activeSystem === "new") {
				return await newProgress.toggleLessonCompletion(moduleId, lessonId);
			}if (activeSystem === "legacy") {
				const nodeId = convertToLegacyNodeId(moduleId, lessonId, mappings);
				return await legacyProgress.toggleLessonCompletion(nodeId);
			}
			return Promise.resolve();
		},

		// Mark lesson as completed (unified interface)
		markLessonCompleted: async (moduleId, lessonId) => {
			if (activeSystem === "new") {
				return await newProgress.markLessonCompleted(moduleId, lessonId);
			}if (activeSystem === "legacy") {
				const nodeId = convertToLegacyNodeId(moduleId, lessonId, mappings);
				return await legacyProgress.toggleLessonCompletion(nodeId);
			}
			return Promise.resolve();
		},

		// Mark lesson as in progress (unified interface)
		markLessonInProgress: async (moduleId, lessonId) => {
			if (activeSystem === "new") {
				return await newProgress.markLessonInProgress(moduleId, lessonId);
			}if (activeSystem === "legacy") {
				// Legacy system doesn't have explicit "in progress" - just mark as not completed
				return Promise.resolve();
			}
			return Promise.resolve();
		},

		// Get module progress (new system only)
		getModuleProgress: (moduleId) => {
			if (activeSystem === "new") {
				return newProgress.getModuleProgress(moduleId);
			}
			return getDefaultModuleProgress();
		},

		// Refresh progress data
		refreshProgress: async () => {
			if (activeSystem === "new") {
				return await newProgress.refreshProgress();
			}if (activeSystem === "legacy") {
				return await legacyProgress.fetchAllProgressData(roadmapId);
			}
			return Promise.resolve();
		},

		// Raw access to underlying systems (for migration purposes)
		rawNewProgress: newProgress,
		rawLegacyProgress: legacyProgress,

		// Migration utilities
		migrationUtils: {
			async migrateFromLegacyToNew() {
				if (activeSystem !== "legacy" || !courseId) {
					throw new Error(
						"Migration only available from legacy system with valid courseId",
					);
				}

				try {
					// Get legacy data
					const legacyData = legacyProgress.lessonStatuses;

					// Convert to new format
					const migrationPromises = Object.entries(legacyData).map(
						async ([nodeId, status]) => {
							const { moduleId, lessonId } = convertFromLegacyNodeId(
								nodeId,
								mappings,
							);
							if (moduleId && lessonId) {
								const newStatus = progressUtils.convertLegacyStatus(status);
								// Would need to call new progress API here
								return { moduleId, lessonId, status: newStatus };
							}
							return null;
						},
					);

					const migrationResults = await Promise.all(migrationPromises);
					const validMigrations = migrationResults.filter(Boolean);

					setMigrationData({
						migratedCount: validMigrations.length,
						totalCount: Object.keys(legacyData).length,
						results: validMigrations,
					});

					return validMigrations;
				} catch (error) {
					console.error("Progress migration failed:", error);
					throw error;
				}
			},

			getMigrationData() {
				return migrationData;
			},
		},
	};

	return (
		<ProgressCompatibilityContext.Provider value={unifiedProgress}>
			{children}
		</ProgressCompatibilityContext.Provider>
	);
}

/**
 * Hook to use the unified progress system
 */
export function useUnifiedProgress() {
	const context = useContext(ProgressCompatibilityContext);
	if (context === null) {
		throw new Error(
			"useUnifiedProgress must be used within a ProgressCompatibilityProvider",
		);
	}
	return context;
}

/**
 * Safe version of the unified progress hook
 */
export function useUnifiedProgressSafe() {
	const context = useContext(ProgressCompatibilityContext);
	if (context === null) {
		return {
			activeSystem: "none",
			isNewSystem: false,
			isLegacySystem: false,
			isActiveSystem: false,
			courseProgress: getDefaultProgress(),
			isLoading: false,
			error: null,
			isLessonCompleted: () => false,
			getLessonStatus: () => "not_started",
			toggleLessonCompletion: () => Promise.resolve(),
			markLessonCompleted: () => Promise.resolve(),
			markLessonInProgress: () => Promise.resolve(),
			getModuleProgress: () => getDefaultModuleProgress(),
			refreshProgress: () => Promise.resolve(),
			rawNewProgress: null,
			rawLegacyProgress: null,
			migrationUtils: {
				migrateFromLegacyToNew: () =>
					Promise.reject(new Error("No active progress system")),
				getMigrationData: () => ({}),
			},
		};
	}
	return context;
}

// Helper functions

function getDefaultProgress() {
	return {
		totalModules: 0,
		completedModules: 0,
		inProgressModules: 0,
		totalLessons: 0,
		completedLessons: 0,
		progressPercentage: 0,
	};
}

function getDefaultModuleProgress() {
	return {
		totalLessons: 0,
		completedLessons: 0,
		inProgressLessons: 0,
		progressPercentage: 0,
	};
}

function adaptLegacyProgressToCourse(legacyProgress) {
	if (!legacyProgress) return getDefaultProgress();

	return {
		totalModules: 1, // Legacy system treats roadmap as single module
		completedModules: legacyProgress.progressPercentage === 100 ? 1 : 0,
		inProgressModules:
			legacyProgress.progressPercentage > 0 &&
			legacyProgress.progressPercentage < 100
				? 1
				: 0,
		totalLessons: legacyProgress.totalLessons || 0,
		completedLessons: legacyProgress.completedLessons || 0,
		progressPercentage: legacyProgress.progressPercentage || 0,
	};
}

function convertToLegacyNodeId(moduleId, lessonId, mappings) {
	// Check if we have a direct mapping
	const mappingKey = `${moduleId}:${lessonId}`;
	if (mappings[mappingKey]) {
		return mappings[mappingKey];
	}

	// Fallback: use lessonId as nodeId
	return lessonId;
}

function convertFromLegacyNodeId(nodeId, mappings) {
	// Check reverse mappings
	for (const [newKey, legacyId] of Object.entries(mappings)) {
		if (legacyId === nodeId) {
			const [moduleId, lessonId] = newKey.split(":");
			return { moduleId, lessonId };
		}
	}

	// Fallback: treat nodeId as lessonId with unknown moduleId
	return { moduleId: null, lessonId: nodeId };
}

/**
 * Higher-order component to provide progress compatibility
 */
export function withProgressCompatibility(Component, options = {}) {
	return function ProgressCompatibleComponent(props) {
		const { courseId, roadmapId, useNewProgress, useLegacyProgress, mappings } =
			{ ...options, ...props };

		return (
			<ProgressCompatibilityProvider
				courseId={courseId}
				roadmapId={roadmapId}
				useNewProgress={useNewProgress}
				useLegacyProgress={useLegacyProgress}
				mappings={mappings}
			>
				<Component {...props} />
			</ProgressCompatibilityProvider>
		);
	};
}

/**
 * Hook for automatic progress system detection
 */
export function useProgressSystemDetection(context = {}) {
	const { courseId, roadmapId, moduleId, lessonId, nodeId } = context;

	const detection = {
		hasNewContext: Boolean(courseId && moduleId),
		hasLegacyContext: Boolean(roadmapId || nodeId),
		recommendedSystem: null,
		confidence: 0,
	};

	if (detection.hasNewContext && !detection.hasLegacyContext) {
		detection.recommendedSystem = "new";
		detection.confidence = 0.9;
	} else if (detection.hasLegacyContext && !detection.hasNewContext) {
		detection.recommendedSystem = "legacy";
		detection.confidence = 0.9;
	} else if (detection.hasNewContext && detection.hasLegacyContext) {
		// Both contexts available - prefer new system
		detection.recommendedSystem = "new";
		detection.confidence = 0.7;
	} else {
		detection.recommendedSystem = "none";
		detection.confidence = 0;
	}

	return detection;
}
