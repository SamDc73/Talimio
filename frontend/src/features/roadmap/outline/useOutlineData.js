// Loads and normalizes the roadmap data for Outline mode

import { useEffect, useState } from "react";

/**
 * Fetches and normalizes roadmap data for the outline view.
 * @param {string} roadmapId - The ID of the roadmap to fetch.
 * @returns {Object} - Object containing modules array and loading/error states
 */
export function useOutlineData(roadmapId) {
	const [modules, setModules] = useState([]);
	const [isLoading, setIsLoading] = useState(false);
	const [error, setError] = useState(null);

	useEffect(() => {
		if (!roadmapId) {
			setModules([]);
			return;
		}

		async function fetchData() {
			setIsLoading(true);
			setError(null);
			try {
				const res = await fetch(
					`${import.meta.env.VITE_API_BASE || '/api/v1'}/roadmaps/${roadmapId}`,
				);
				if (!res.ok) {
					throw new Error(`HTTP error! status: ${res.status}`);
				}
				const data = await res.json();

				if (!data || !data.nodes) {
					console.warn("API response missing nodes");
					setModules([]);
					return;
				}

				// Create a map of all nodes for easy lookup
				const nodeMap = new Map(data.nodes.map((node) => [node.id, node]));

				// Recursive function to normalize a node and all its children
				const normalizeNode = (node) => ({
					id: node.id,
					title: node.title || "Untitled",
					description: node.description || "",
					order: node.order || 0,
					status: node.status || "not_started",
					// Recursively normalize all children (if any)
					lessons: node.children
						? node.children
								.sort((a, b) => (a.order || 0) - (b.order || 0))
								.map((child) => normalizeNode(child))
						: [],
				});

				// Find root nodes (those without parentId)
				const rootNodes = data.nodes.filter((node) => !node.parentId);

				// Process and sort root nodes
				const normalizedModules = rootNodes
					.map((node) => normalizeNode(node))
					.sort((a, b) => (a.order || 0) - (b.order || 0));

				setModules(normalizedModules);
			} catch (err) {
				console.error("Failed to load or parse roadmap data:", err);
				setError(err.message || "Failed to load data");
				setModules([]);
			} finally {
				setIsLoading(false);
			}
		}

		fetchData();
	}, [roadmapId]);

	return { modules, isLoading, error };
}
