import {
	createContext,
	useContext,
	useEffect,
	useState,
	useCallback,
} from "react";
import { updateLessonStatus } from "../services/progressService";
import { getCourseWithModules } from "../utils/courseDetection";
import { useToast } from "./use-toast";

const ProgressContext = createContext(null);

export function ProgressProvider({ children, courseId, isCourseMode = false }) {
	const [lessonStatuses, setLessonStatuses] = useState({});
	const [courseProgress, setCourseProgress] = useState({
		totalLessons: 0,
		completedLessons: 0,
		progressPercentage: 0,
	});
	const [isLoading, setIsLoading] = useState(false);
	const [error, setError] = useState(null);
	const [_detectedCourseMode, setDetectedCourseMode] = useState(null);
	const { toast } = useToast();
	
	// Note: We use getCourseWithModules for consistent course data fetching

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
				"isCourseMode:",
				isCourseMode,
			);
			setIsLoading(true);
			setError(null);

			try {
				// Use course data fetching - assumes we're in course mode
				const { modules } = await getCourseWithModules(currentCourseId);
				
				// Store detected mode for use in other functions - always true for course API
				const detectedMode = true;
				setDetectedCourseMode(detectedMode);
				
				// Validate modules array
				if (!Array.isArray(modules)) {
					throw new Error(`Invalid modules data: expected array, got ${typeof modules}`);
				}

				// For course mode, we need to collect all lessons from all modules
				let allLessons = [];
				if (detectedMode) {
					// Course mode: flatten the hierarchy (modules -> lessons)
					for (const module of modules) {
						// Add the module itself as a lesson
						allLessons.push({
							id: module.id,
							status: module.status || "not_started",
							title: module.title
						});
						
						// Add all sub-lessons
						if (module.lessons && Array.isArray(module.lessons)) {
							for (const lesson of module.lessons) {
								allLessons.push({
									id: lesson.id,
									status: lesson.status || "not_started",
									title: lesson.title
								});
							}
						}
					}
				} else {
					// Legacy mode: modules are the lessons
					allLessons = modules.map(module => ({
						id: module.id,
						status: module.status || "not_started",
						title: module.title
					}));
				}

				// Transform to lesson statuses format
				const statusMap = {};
				for (const lesson of allLessons) {
					statusMap[lesson.id] = lesson.status;
				}
				setLessonStatuses(statusMap);

				// Calculate progress from all lessons
				const totalLessons = allLessons.length;
				const completedLessons = allLessons.filter(
					(lesson) => lesson.status === "completed",
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
		[toast, isCourseMode],
	);

	useEffect(() => {
		fetchAllProgressData(courseId);
	}, [courseId, fetchAllProgressData]);

	const toggleLessonCompletion = useCallback(
		async (lessonId, moduleId) => {
			if (!courseId || !moduleId) return;

			const originalLessonStatuses = { ...lessonStatuses };
			const originalCourseProgress = { ...courseProgress };

			try {
				const currentStatus = lessonStatuses[lessonId] || "not_started";
				const newStatus = currentStatus === "completed" ? "not_started" : "completed";

				// Update UI immediately
				setLessonStatuses((prev) => ({
					...prev,
					[lessonId]: newStatus,
				}));

				// Calculate client-side progress for immediate feedback
				const completedDelta = newStatus === "completed" ? 1 : -1;
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
				const updatePromise = updateLessonStatus(courseId, moduleId, lessonId, newStatus);
					
				updatePromise.catch((err) => {
					console.error("Failed to update lesson status:", err);
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
			return lessonStatuses[lessonId] === "completed";
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
