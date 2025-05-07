import { useEffect, useState } from 'react';
import { useToast } from './use-toast';
import { getCourseProgress, getLessonStatuses, updateLessonStatus } from '../services/progressApi';

/**
 * Custom hook to manage lesson progress state and API interactions
 *
 * @param {string} courseId - The ID of the course
 * @returns {Object} Progress state and functions
 */
export function useProgress(courseId) {
  const [lessonStatuses, setLessonStatuses] = useState({});
  const [courseProgress, setCourseProgress] = useState({
    total_lessons: 0,
    completed_lessons: 0,
    progress_percentage: 0
  });
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);
  const { toast } = useToast();

  // Fetch lesson statuses on mount and when courseId changes
  useEffect(() => {
    if (!courseId) return;

    const fetchData = async () => {
      setIsLoading(true);
      setError(null);

      try {
        // Fetch lesson statuses
        const statusesResponse = await getLessonStatuses(courseId);

        // Convert array of lesson statuses to a map for easier lookup
        const statusMap = {};
        for (const lesson of statusesResponse.lessons) {
          statusMap[lesson.id] = lesson.status;
        }

        setLessonStatuses(statusMap);

        // Fetch course progress
        const progressResponse = await getCourseProgress(courseId);
        setCourseProgress(progressResponse);
      } catch (err) {
        setError(err);
        toast({
          title: 'Error',
          description: err.message || 'Failed to fetch progress data',
          variant: 'destructive',
        });
      } finally {
        setIsLoading(false);
      }
    };

    fetchData();
  }, [courseId, toast]);

  /**
   * Toggle a lesson's completion status
   *
   * @param {string} lessonId - The ID of the lesson
   * @returns {Promise<void>}
   */
  const toggleLessonCompletion = async (lessonId) => {
    try {
      const currentStatus = lessonStatuses[lessonId] || 'not_started';
      // Toggle between 'done' and 'not_started'
      const newStatus = currentStatus === 'done' ? 'not_started' : 'done';

      // Optimistically update lesson status in UI
      setLessonStatuses(prev => ({
        ...prev,
        [lessonId]: newStatus
      }));

      // Also optimistically update the course progress percentage
      // Calculate the new completed count based on the action (completing or uncompleting)
      const completedDelta = newStatus === 'done' ? 1 : -1;
      const newCompletedLessons = Math.max(0, (courseProgress.completed_lessons || 0) + completedDelta);
      const totalLessons = courseProgress.total_lessons || Object.keys(lessonStatuses).length || 1;
      const newPercentage = Math.round((newCompletedLessons / totalLessons) * 100);

      // Update the course progress state optimistically
      setCourseProgress(prev => ({
        ...prev,
        completed_lessons: newCompletedLessons,
        progress_percentage: newPercentage
      }));

      // Update backend
      await updateLessonStatus(lessonId, newStatus);

      // Refresh course progress from backend to ensure accuracy
      const progressResponse = await getCourseProgress(courseId);
      setCourseProgress(progressResponse);

      // Removed toast notification for successful status updates
    } catch (err) {
      // Revert optimistic updates on error
      setLessonStatuses(prev => ({
        ...prev,
        [lessonId]: lessonStatuses[lessonId] || 'not_started'
      }));

      // Also revert the course progress
      const progressResponse = await getCourseProgress(courseId).catch(() => courseProgress);
      setCourseProgress(progressResponse);

      // Keep error toast for failed updates
      toast({
        title: 'Error',
        description: err.message || 'Failed to update lesson status',
        variant: 'destructive',
      });
    }
  };

  /**
   * Check if a lesson is completed
   *
   * @param {string} lessonId - The ID of the lesson
   * @returns {boolean} True if the lesson is completed
   */
  const isLessonCompleted = (lessonId) => {
    return lessonStatuses[lessonId] === 'done';
  };

  return {
    lessonStatuses,
    courseProgress,
    isLoading,
    error,
    toggleLessonCompletion,
    isLessonCompleted,
  };
}
