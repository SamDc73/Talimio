import { useEffect } from "react";
import { api } from "@/lib/apiClient";

export function useCourseProgressSync(setContentItems) {
	// Listen for course progress updates with throttling to prevent cascading updates
	useEffect(() => {
		let refreshTimeout = null;

		const handleCourseProgressRefresh = async (event) => {
			// Clear any pending refresh
			if (refreshTimeout) {
				clearTimeout(refreshTimeout);
			}

			// Throttle refresh to prevent cascading updates and infinite loops
			refreshTimeout = setTimeout(async () => {
				const { courseId } = event.detail;
				console.log(
					`🔄 Course progress refresh triggered for course ${courseId}`,
				);

				// Refetch the specific course's progress and update only that course in contentItems
				try {
					const response = await api.get(`/courses/${courseId}/progress`);
					const updatedProgress = response.completion_percentage || 0;

					// Update only the specific course in contentItems
					setContentItems((prevItems) =>
						prevItems.map((item) =>
							item.type === "course" && item.id === courseId
								? { ...item, progress: updatedProgress }
								: item,
						),
					);
				} catch (error) {
					console.error(
						`Failed to refresh progress for course ${courseId}:`,
						error,
					);
				}
			}, 500); // 500ms throttle to prevent rapid refreshes
		};

		// Add event listener
		window.addEventListener(
			"courseProgressRefresh",
			handleCourseProgressRefresh,
		);

		// Cleanup
		return () => {
			if (refreshTimeout) {
				clearTimeout(refreshTimeout);
			}
			window.removeEventListener(
				"courseProgressRefresh",
				handleCourseProgressRefresh,
			);
		};
	}, [setContentItems]);

	// Also listen for course progress updates (when progress is explicitly set) with throttling
	useEffect(() => {
		let updateTimeout = null;

		const handleCourseProgressUpdate = (event) => {
			// Clear any pending update
			if (updateTimeout) {
				clearTimeout(updateTimeout);
			}

			// Throttle updates to prevent cascading updates and infinite loops
			updateTimeout = setTimeout(() => {
				const { courseId, progressStats } = event.detail;
				console.log(
					`📊 Course progress updated for course ${courseId}:`,
					progressStats,
				);

				// Update the specific course in contentItems with the new progress
				setContentItems((prevItems) =>
					prevItems.map((item) =>
						item.type === "course" && item.id === courseId
							? { ...item, progress: progressStats.completion_percentage || 0 }
							: item,
					),
				);
			}, 300); // 300ms throttle for updates
		};

		// Add event listener
		window.addEventListener("courseProgressUpdate", handleCourseProgressUpdate);

		// Cleanup
		return () => {
			if (updateTimeout) {
				clearTimeout(updateTimeout);
			}
			window.removeEventListener(
				"courseProgressUpdate",
				handleCourseProgressUpdate,
			);
		};
	}, [setContentItems]);
}
