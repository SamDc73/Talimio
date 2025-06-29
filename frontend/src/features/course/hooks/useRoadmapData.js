import { useCallback, useEffect, useState } from "react";
import { useCourseService } from "../api/courseApi";

/**
 * Common hook for fetching course data with module progress
 * This can be used by both map and outline views
 *
 * @param {string} courseId - The ID of the course to fetch
 * @returns {Object} - Object containing course data, modules, and utility functions
 */
export function useRoadmapData(courseId) {
	const [roadmap, setRoadmap] = useState(null);
	const [nodes, setNodes] = useState([]);
	const [isLoading, setIsLoading] = useState(false);
	const [error, setError] = useState(null);

	// Use course service for all operations
	const courseService = useCourseService(courseId);

	// Fetch course basic info
	const fetchRoadmap = useCallback(async () => {
		if (!courseId) {
			setRoadmap(null);
			return;
		}

		try {
			// Use course API
			const data = await courseService.fetchCourse();
			setRoadmap(data);
		} catch (err) {
			console.error("Failed to load course:", err);
			throw err;
		}
		// eslint-disable-next-line react-hooks/exhaustive-deps
	}, [courseId, courseService.fetchCourse]); // Only depend on courseId

	// Fetch modules with progress
	const fetchNodes = useCallback(async () => {
		if (!courseId) {
			setNodes([]);
			return;
		}

		try {
			// Use course API
			const moduleData = await courseService.fetchModules();
			setNodes(moduleData || []);
		} catch (err) {
			console.error("Failed to load modules:", err);
			throw err;
		}
		// eslint-disable-next-line react-hooks/exhaustive-deps
	}, [courseId, courseService.fetchModules]); // Only depend on courseId

	// Update module status optimistically
	const updateNode = useCallback(
		async (nodeId, status) => {
			// Optimistic update
			setNodes((prev) =>
				prev.map((node) =>
					node.id === nodeId
						? {
								...node,
								status,
								completionPercentage:
									status === "completed"
										? 100
										: status === "in_progress"
											? 50
											: 0,
							}
						: node,
				),
			);

			try {
				// Use course API
				await courseService.updateModule(nodeId, { status });
				// Refetch to ensure consistency
				await fetchNodes();
			} catch (err) {
				console.error("Failed to update module status:", err);
				// Revert optimistic update on failure
				await fetchNodes();
				throw err;
			}
		},
		// eslint-disable-next-line react-hooks/exhaustive-deps
		[fetchNodes, courseService.updateModule], // Only depend on fetchNodes, not courseService
	);

	// Main data fetching effect
	useEffect(() => {
		if (!courseId) {
			setRoadmap(null);
			setNodes([]);
			return;
		}

		async function fetchData() {
			setIsLoading(true);
			setError(null);
			try {
				await Promise.all([fetchRoadmap(), fetchNodes()]);
			} catch (err) {
				console.error("Failed to load course data:", err);
				setError(err.message || "Failed to load course data");
				setRoadmap(null);
				setNodes([]);
			} finally {
				setIsLoading(false);
			}
		}

		fetchData();
	}, [courseId, fetchRoadmap, fetchNodes]);

	// Calculate overall progress
	const overallProgress =
		nodes.length > 0
			? Math.round(
					(nodes.filter((n) => n.status === "completed").length /
						nodes.length) *
						100,
				)
			: 0;

	return {
		roadmap,
		nodes,
		isLoading,
		error,
		overallProgress,
		updateNode,
		refresh: () => {
			fetchRoadmap();
			fetchNodes();
		},
	};
}
