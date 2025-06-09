import React, {
	createContext,
	useContext,
	useEffect,
	useState,
	useCallback,
} from "react";
import { getRoadmapNodes, updateNodeStatus } from "../services/progressService";
import { useToast } from "./use-toast";

const ProgressContext = createContext(null);

export function ProgressProvider({ children, courseId }) {
	const [lessonStatuses, setLessonStatuses] = useState({});
	const [courseProgress, setCourseProgress] = useState({
		totalLessons: 0,
		completedLessons: 0,
		progressPercentage: 0,
	});
	const [isLoading, setIsLoading] = useState(false);
	const [error, setError] = useState(null);
	const { toast } = useToast();

	const fetchAllProgressData = useCallback(
		async (currentCourseId) => {
			if (!currentCourseId) {
				console.log("ProgressProvider - no courseId provided, skipping fetch");
				setLessonStatuses({});
				setCourseProgress({
					totalLessons: 0,
					completedLessons: 0,
					progressPercentage: 0,
				});
				return;
			}

			console.log(
				"ProgressProvider - starting data fetch for courseId:",
				currentCourseId,
			);
			setIsLoading(true);
			setError(null);

			try {
				const nodes = await getRoadmapNodes(currentCourseId);

				// Transform nodes to lesson statuses format
				const statusMap = {};
				for (const node of nodes) {
					statusMap[node.id] = node.status || "not_started";
				}
				setLessonStatuses(statusMap);

				// Calculate progress from nodes
				const totalLessons = nodes.length;
				const completedLessons = nodes.filter(
					(node) => node.status === "done",
				).length;
				const progressPercentage =
					totalLessons > 0
						? Math.round((completedLessons / totalLessons) * 100)
						: 0;

				const progressResponse = {
					courseId: currentCourseId,
					totalLessons: totalLessons,
					completedLessons: completedLessons,
					progressPercentage: progressPercentage,
				};

				console.log("ProgressProvider - progress response:", progressResponse);
				setCourseProgress(progressResponse);
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
		[toast],
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
				const newCompletedLessons = Math.max(
					0,
					courseProgress.completedLessons + completedDelta,
				);
				const newPercentage = Math.round(
					(newCompletedLessons / courseProgress.totalLessons) * 100,
				);

				setCourseProgress((prev) => ({
					...prev,
					completedLessons: newCompletedLessons,
					progressPercentage: newPercentage,
				}));

				// Update server in background without waiting
				updateNodeStatus(lessonId, newStatus).catch((err) => {
					console.error("Failed to update node status:", err);
					// Revert on error
					setLessonStatuses(originalLessonStatuses);
					setCourseProgress(originalCourseProgress);
					toast({
						title: "Error updating lesson",
						description:
							"Failed to update lesson status. Your progress has been reverted.",
						variant: "destructive",
					});
				});
			} catch (err) {
				setLessonStatuses(originalLessonStatuses);
				setCourseProgress(originalCourseProgress);
				toast({
					title: "Error updating lesson",
					description:
						err.message ||
						"Failed to update lesson status. Your progress has been reverted to the last saved state.",
					variant: "destructive",
				});
			}
		},
		[courseId, lessonStatuses, courseProgress, toast],
	);

	const isLessonCompleted = useCallback(
		(lessonId) => {
			return lessonStatuses[lessonId] === "done";
		},
		[lessonStatuses],
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

	return (
		<ProgressContext.Provider value={value}>
			{children}
		</ProgressContext.Provider>
	);
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
