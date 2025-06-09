import { getRoadmapNodes, updateNodeStatus } from "@/services/progressService";
import { useCallback, useEffect, useState } from "react";

const BASE_URL =
	import.meta.env.VITE_API_BASE_URL || "http://localhost:8080/api/v1";

/**
 * Common hook for fetching roadmap data with node progress
 * This can be used by both map and outline views
 *
 * @param {string} roadmapId - The ID of the roadmap to fetch
 * @returns {Object} - Object containing roadmap data, nodes, and utility functions
 */
export function useRoadmapData(roadmapId) {
	const [roadmap, setRoadmap] = useState(null);
	const [nodes, setNodes] = useState([]);
	const [isLoading, setIsLoading] = useState(false);
	const [error, setError] = useState(null);

	// Fetch roadmap basic info
	const fetchRoadmap = useCallback(async () => {
		if (!roadmapId) {
			setRoadmap(null);
			return;
		}

		try {
			const response = await fetch(`${BASE_URL}/roadmaps/${roadmapId}`);
			if (!response.ok) {
				throw new Error(`HTTP error! status: ${response.status}`);
			}
			const data = await response.json();
			setRoadmap(data);
		} catch (err) {
			console.error("Failed to load roadmap:", err);
			throw err;
		}
	}, [roadmapId]);

	// Fetch nodes with progress using new endpoint
	const fetchNodes = useCallback(async () => {
		if (!roadmapId) {
			setNodes([]);
			return;
		}

		try {
			const nodeData = await getRoadmapNodes(roadmapId);
			setNodes(nodeData || []);
		} catch (err) {
			console.error("Failed to load roadmap nodes:", err);
			throw err;
		}
	}, [roadmapId]);

	// Update node status optimistically
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
				await updateNodeStatus(nodeId, status);
				// Refetch to ensure consistency
				await fetchNodes();
			} catch (err) {
				console.error("Failed to update node status:", err);
				// Revert optimistic update on failure
				await fetchNodes();
				throw err;
			}
		},
		[fetchNodes],
	);

	// Main data fetching effect
	useEffect(() => {
		if (!roadmapId) {
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
				console.error("Failed to load roadmap data:", err);
				setError(err.message || "Failed to load data");
				setRoadmap(null);
				setNodes([]);
			} finally {
				setIsLoading(false);
			}
		}

		fetchData();
	}, [roadmapId, fetchRoadmap, fetchNodes]);

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
