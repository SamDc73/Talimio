import useAppStore, {
	selectSidebarOpen,
	selectToggleSidebar,
} from "@/stores/useAppStore";
import { useCourseProgress } from "../../hooks/useCourseProgress";
import { CourseHeader } from "./CourseHeader";

/**
 * Application header component that provides navigation controls
 *
 * Features:
 * - Collapsible sidebar toggle
 * - Course title display with gradient styling
 * - View mode toggle between map and outline representations
 *
 * The header stays fixed at the top and includes a subtle blur effect for better readability
 * when content scrolls underneath.
 *
 * @param {Object} props
 * @param {string} props.courseName - Course title to display in the header
 * @param {string} props.mode - Current view mode ("visual" for map flowchart or "outline" for text)
 * @param {function} props.onModeChange - Callback handler for mode toggle changes
 * @param {string} props.courseId - ID of the current course
 */
function RoadmapHeader({ courseName, mode, onModeChange, courseId }) {
	const isOpen = useAppStore(selectSidebarOpen);
	const toggleSidebar = useAppStore(selectToggleSidebar);
	// Use the progress hook to get real-time course progress updates
	const { progress: courseProgress } = useCourseProgress(courseId);

	// Calculate progress percentage, defaulting to 0 if not available
	const progress = courseProgress?.percentage || 0;

	return (
		<CourseHeader
			courseName={courseName}
			mode={mode}
			onModeChange={onModeChange}
			courseId={courseId}
			progress={progress}
			isOpen={isOpen}
			toggleSidebar={toggleSidebar}
		/>
	);
}

export default RoadmapHeader;
