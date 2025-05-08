import { useEffect, useState } from "react";

/**
 * Common hook for fetching roadmap data
 * This can be used by both map and outline views
 * 
 * @param {string} roadmapId - The ID of the roadmap to fetch
 * @returns {Object} - Object containing roadmap data and loading/error states
 */
export function useRoadmapData(roadmapId) {
  const [roadmap, setRoadmap] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!roadmapId) {
      setRoadmap(null);
      return;
    }

    async function fetchData() {
      setIsLoading(true);
      setError(null);
      try {
        const response = await fetch(`http://localhost:8080/api/v1/roadmaps/${roadmapId}`);
        if (!response.ok) {
          throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data = await response.json();
        setRoadmap(data);
      } catch (err) {
        console.error("Failed to load roadmap data:", err);
        setError(err.message || "Failed to load data");
        setRoadmap(null);
      } finally {
        setIsLoading(false);
      }
    }

    fetchData();
  }, [roadmapId]);

  return { roadmap, isLoading, error };
}
