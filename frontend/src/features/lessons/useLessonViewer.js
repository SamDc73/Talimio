import { useToast } from "@/hooks/use-toast";
import { useState } from "react";
import { fetchLessonsByNodeId, generateLesson } from "./lessonsApi";

/**
 * Hook to handle lesson viewing and generation.
 * Checks if a lesson exists for a node, and if not, generates one.
 *
 * @returns {Object} Hook state and functions
 */
export function useLessonViewer() {
  const [lesson, setLesson] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);
  const { toast } = useToast();

  /**
   * Get or generate a lesson for a node
   * @param {string} nodeId - The ID of the node
   * @param {Object} nodeMeta - Metadata about the node (title, description, etc.)
   */
  const getOrGenerateLesson = async (nodeId, nodeMeta) => {
    setIsLoading(true);
    setError(null);

    try {
      // Ensure nodeId is a string
      const nodeIdStr = String(nodeId);

      // First, try to fetch existing lessons for this node
      const existingLessons = await fetchLessonsByNodeId(nodeIdStr);

      // If we have lessons, use the most recent one
      if (existingLessons && existingLessons.length > 0) {
        setLesson(existingLessons[0]); // Assuming they're sorted by created_at DESC
        return existingLessons[0];
      }

      // No existing lessons, generate a new one
      toast({
        title: "Generating lesson",
        description: "No existing lesson found. Generating a new one...",
      });

      console.log("Generating lesson for node:", nodeIdStr);

      const newLesson = await generateLesson({
        course_id: nodeIdStr,
        slug: `lesson-${nodeIdStr}`,
        node_meta: nodeMeta || {
          title: "Learning Topic",
          description: "A comprehensive lesson on this topic",
          skill_level: "beginner",
        },
      });

      setLesson(newLesson);
      toast({
        title: "Lesson generated",
        description: "Your lesson is ready to view",
      });

      return newLesson;
    } catch (err) {
      const message = err.message || "Failed to load or generate lesson";
      setError(message);
      toast({
        title: "Error",
        description: message,
        variant: "destructive",
      });
      throw err;
    } finally {
      setIsLoading(false);
    }
  };

  /**
   * Clear the current lesson
   */
  const clearLesson = () => {
    setLesson(null);
    setError(null);
  };

  return {
    lesson,
    isLoading,
    error,
    getOrGenerateLesson,
    clearLesson,
  };
}
