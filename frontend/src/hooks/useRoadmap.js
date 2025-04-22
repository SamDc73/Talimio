import { useApi } from "./useApi";

export function useRoadmap() {
  const { execute: executeCreateRoadmap } = useApi("/api/v1/roadmaps", {
    method: "POST",
  });

  const { execute: executeGetRoadmap } = useApi("");

  const createRoadmap = async (data) => {
    try {
      const response = await executeCreateRoadmap(data);
      return response;
    } catch (error) {
      console.error("Error creating roadmap:", error);
      throw error;
    }
  };

  const getRoadmap = async (id) => {
    if (!id) throw new Error("Roadmap ID is required");

    const response = await executeGetRoadmap(null, {
      url: `/api/v1/roadmaps/${id}`,
      method: "GET",
    });

    if (!response) throw new Error("Failed to fetch roadmap");
    return response;
  };

  return {
    createRoadmap,
    getRoadmap,
  };
}
