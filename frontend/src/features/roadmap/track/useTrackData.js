import { useEffect, useState } from "react";

/**
 * Fetches and normalizes roadmap data for the track view.
 * @param {string} roadmapId - The ID of the roadmap to fetch.
 * @returns {Object} - Object containing modules array and loading/error states
 */
export function useTrackData(roadmapId) {
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
					`${import.meta.env.VITE_API_BASE || "/api/v1"}/roadmaps/${roadmapId}`,
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

				// Map could be used for more complex operations if needed

				// Recursive function to normalize a node and all its children
				const normalizeNode = (node) => ({
					id: node.id,
					title: node.title || "Untitled",
					description: node.description || "",
					order: node.order || 0,
					status: node.status || "not_started",
					// Include the original children array for the track view
					children: node.children || [],
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
