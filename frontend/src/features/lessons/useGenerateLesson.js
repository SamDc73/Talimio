import { useState } from "react";
import { generateLesson as apiGenerateLesson } from "./lessonsApi";

/**
 * Hook to generate a lesson via API.
 * @returns {{ data: Object|null, isLoading: boolean, error: string|null, generate: function }}
 */
export function useGenerateLesson() {
  const [data, setData] = useState(null);
  const [isLoading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const generate = async ({ courseId, slug, nodeMeta }) => {
    setLoading(true);
    setError(null);
    try {
      // Use the API function from lessonsApi.js
      const json = await apiGenerateLesson({
        course_id: courseId,
        slug,
        node_meta: nodeMeta,
      });

      setData(json);
      return json;
    } catch (err) {
      const message = err.message || "Unknown error";
      setError(message);
      throw err;
    } finally {
      setLoading(false);
    }
  };

  return { data, isLoading, error, generate };
}
