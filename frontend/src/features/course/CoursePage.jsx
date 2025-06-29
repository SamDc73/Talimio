import { useEffect } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { LessonViewer } from "./components";
import { useLessonViewer } from "./hooks/useLessonViewer";

const CoursePage = () => {
	const { courseId, lessonId } = useParams();
	const navigate = useNavigate();

	// Use the simplified lesson viewer hook
	const { lesson, isLoading, error, loadLesson, createLesson } =
		useLessonViewer(courseId);

	// Load lesson when component mounts or lessonId changes
	useEffect(() => {
		if (courseId && lessonId) {
			loadLesson(lessonId);
		}
	}, [courseId, lessonId, loadLesson]);

	const handleBack = () => {
		navigate(`/roadmap/${courseId}`);
	};

	const handleRegenerate = async (lessonId) => {
		if (lessonId) {
			await createLesson();
		}
	};

	const handleMarkComplete = (lessonId) => {
		// TODO: Implement mark complete functionality
		console.log("Mark complete:", lessonId);
	};

	if (!courseId || !lessonId) {
		return (
			<div className="flex items-center justify-center h-screen">
				<div className="text-center">
					<h2 className="text-xl font-semibold mb-2">Invalid URL</h2>
					<p className="text-gray-600 mb-4">
						Course and lesson IDs are required.
					</p>
					<button
						type="button"
						onClick={() => navigate("/")}
						className="px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600"
					>
						Go Home
					</button>
				</div>
			</div>
		);
	}

	return (
		<LessonViewer
			lesson={lesson}
			isLoading={isLoading}
			error={error}
			onBack={handleBack}
			onRegenerate={handleRegenerate}
			onMarkComplete={handleMarkComplete}
		/>
	);
};

export default CoursePage;
