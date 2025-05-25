import React, { createContext, useContext, useEffect, useState, useCallback } from "react";
import { useToast } from "./use-toast";
import { getCourseProgress, getLessonStatuses, updateLessonStatus } from "../services/progressApi";

const ProgressContext = createContext(null);

export function ProgressProvider({ children, courseId }) {
  const [lessonStatuses, setLessonStatuses] = useState({});
  const [courseProgress, setCourseProgress] = useState({
    total_lessons: 0,
    completed_lessons: 0,
    progress_percentage: 0,
  });
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);
  const { toast } = useToast();

  const fetchAllProgressData = useCallback(
    async (currentCourseId) => {
      if (!currentCourseId) {
        console.log("ProgressProvider - no courseId provided, skipping fetch");
        setLessonStatuses({});
        setCourseProgress({ total_lessons: 0, completed_lessons: 0, progress_percentage: 0 });
        return;
      }

      console.log("ProgressProvider - starting data fetch for courseId:", currentCourseId);
      setIsLoading(true);
      setError(null);

      try {
        const statusesResponse = await getLessonStatuses(currentCourseId);
        const statusMap = {};
        for (const lesson of statusesResponse?.lessons ?? []) {
          statusMap[lesson.id] = lesson.status;
        }
        setLessonStatuses(statusMap);

        const progressResponse = await getCourseProgress(currentCourseId);
        console.log("ProgressProvider - progress response:", progressResponse);
        setCourseProgress(progressResponse || { total_lessons: 0, completed_lessons: 0, progress_percentage: 0 });
      } catch (err) {
        console.error("ProgressProvider - fetch error:", err);
        setError(err);
        toast({
          title: "Error",
          description: err.message || "Failed to fetch progress data",
          variant: "destructive",
        });
      } finally {
        setIsLoading(false);
      }
    },
    [toast]
  );

  useEffect(() => {
    fetchAllProgressData(courseId);
  }, [courseId, fetchAllProgressData]);

  const toggleLessonCompletion = useCallback(
    async (lessonId) => {
      if (!courseId) return;

      const originalLessonStatuses = { ...lessonStatuses };
      const originalCourseProgress = { ...courseProgress };

      try {
        const currentStatus = lessonStatuses[lessonId] || "not_started";
        const newStatus = currentStatus === "done" ? "not_started" : "done";

        // Update UI immediately
        setLessonStatuses((prev) => ({
          ...prev,
          [lessonId]: newStatus,
        }));

        // Calculate client-side progress for immediate feedback
        const completedDelta = newStatus === "done" ? 1 : -1;
        const newCompletedLessons = Math.max(0, courseProgress.completed_lessons + completedDelta);
        const newPercentage = Math.round((newCompletedLessons / courseProgress.total_lessons) * 100);

        setCourseProgress((prev) => ({
          ...prev,
          completed_lessons: newCompletedLessons,
          progress_percentage: newPercentage,
        }));

        // Update server in background without waiting
        updateLessonStatus(lessonId, newStatus).catch((err) => {
          console.error("Failed to update lesson status:", err);
          // Revert on error
          setLessonStatuses(originalLessonStatuses);
          setCourseProgress(originalCourseProgress);
          toast({
            title: "Error updating lesson",
            description: "Failed to update lesson status. Your progress has been reverted.",
            variant: "destructive",
          });
        });
      } catch (err) {
        setLessonStatuses(originalLessonStatuses);
        setCourseProgress(originalCourseProgress);
        toast({
          title: "Error updating lesson",
          description:
            err.message || "Failed to update lesson status. Your progress has been reverted to the last saved state.",
          variant: "destructive",
        });
      }
    },
    [courseId, lessonStatuses, courseProgress, toast]
  );

  const isLessonCompleted = useCallback(
    (lessonId) => {
      return lessonStatuses[lessonId] === "done";
    },
    [lessonStatuses]
  );

  const value = {
    lessonStatuses,
    courseProgress,
    isLoading,
    error,
    toggleLessonCompletion,
    isLessonCompleted,
    fetchAllProgressData,
  };

  return <ProgressContext.Provider value={value}>{children}</ProgressContext.Provider>;
}

export function useProgress() {
  const context = useContext(ProgressContext);
  if (context === null) {
    throw new Error("useProgress must be used within a ProgressProvider");
  }
  return context;
}

// Hook that safely uses progress context (returns null values if not in a provider)
export function useProgressSafe() {
  const context = useContext(ProgressContext);
  if (context === null) {
    return {
      courseProgress: null,
      isLoading: false,
      error: null,
      toggleLessonCompletion: () => {},
      isLessonCompleted: () => false,
      refreshProgress: () => Promise.resolve(),
    };
  }
  return context;
}
