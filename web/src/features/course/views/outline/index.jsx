import { useProgress } from "../../../../hooks/useProgress";
import { useCourseNavigation } from "../../../../utils/navigationUtils";
import OutlineNode from "../../components/navigation/OutlineNode";

/**
 * OutlineView renders the full roadmap outline, with all modules and their lessons
 * @param {Object} props
 * @param {string} props.roadmapId - The ID of the roadmap to display.
 * @param {Array} props.modules - The modules data passed from parent component.
 * @returns {JSX.Element}
 */
function OutlineView({ roadmapId, modules = [] }) {
	const { courseProgress, toggleLessonCompletion, isLessonCompleted } =
		useProgress();
	const { goToLesson } = useCourseNavigation();

	const handleLessonClick = async (_moduleIdx, _lessonIdx, lessonId) => {
		try {
			if (!lessonId) {
				console.error("Lesson ID is missing:", lessonId);
				return;
			}

			// Navigate to the lesson using simplified URL routing
			console.log("Navigating to lesson:", roadmapId, lessonId);
			goToLesson(roadmapId, lessonId);
		} catch (err) {
			console.error("Error handling lesson click:", err);
		}
	};

	if (!modules || modules.length === 0) {
		return (
			<div
				className="fixed inset-0 flex flex-col items-center justify-center min-h-[calc(100vh-4rem)] text-zinc-500"
				style={{ marginLeft: 0, paddingTop: "4rem" }}
			>
				<p>No outline content available for this roadmap.</p>
			</div>
		);
	}

	return (
		<div className="flex-1 p-4 md:p-6 lg:p-8">
			<div className="max-w-4xl mx-auto">
				{modules.map((module, idx) => (
					<OutlineNode
						key={module.id || idx}
						module={module}
						index={idx}
						onLessonClick={(lessonIdx, lessonId) =>
							handleLessonClick(idx, lessonIdx, lessonId)
						}
						isLessonCompleted={isLessonCompleted}
						toggleLessonCompletion={toggleLessonCompletion}
						courseProgress={courseProgress}
					/>
				))}
			</div>
		</div>
	);
}

export default OutlineView;
