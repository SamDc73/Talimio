import { useToast } from "@/hooks/use-toast";
import { useState, useCallback } from "react";
import { fetchLesson, } from "../api/lessonsApi";

/**
 *  lesson viewer hook
 */
export function useLessonViewer(courseId) {
	const [lesson, setLesson] = useState(null);
	const [isLoading, setIsLoading] = useState(false);
	const [error, setError] = useState(null);
	const { toast } = useToast();

	/**
	 * Load a lesson by ID, generate if needed
	 */
	const loadLesson = useCallback(async (lessonId) => {
		if (!courseId || !lessonId) {
			setError("Missing required IDs");
			return;
		}

		setIsLoading(true);
		setError(null);

		try {
			const lessonData = await fetchLesson(courseId, lessonId);
			setLesson(lessonData);
		} catch (err) {
			setError(err.message);
			toast({
				title: "Error",
				description: err.message,
				variant: "destructive",
			});
		} finally {
			setIsLoading(false);
		}
	}, [courseId, toast]);

	/**
	 * Generate a new lesson (requires moduleId, so disabled for now)
	 */
	const createLesson = useCallback(async () => {
		toast({
			title: "Feature not available",
			description: "Lesson generation requires module selection",
			variant: "destructive",
		});
	}, [toast]);

	/**
	 * Clear the current lesson
	 */
	const clearLesson = useCallback(() => {
		setLesson(null);
		setError(null);
	}, []);

	return {
		lesson,
		isLoading,
		error,
		loadLesson,
		createLesson,
		clearLesson,
	};
}
