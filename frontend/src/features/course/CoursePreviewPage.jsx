import { ArrowLeft, BookOpen } from "lucide-react";
import { useNavigate, useParams } from "react-router-dom";
import { Button } from "@/components/button";
import { MainHeader } from "@/components/header/MainHeader";

const CoursePreviewPage = () => {
	const { courseId } = useParams();
	const navigate = useNavigate();

	const handleBack = () => {
		navigate("/");
	};

	const handleStartCourse = () => {
		navigate(`/course/${courseId}`);
	};

	if (!courseId) {
		return <div>No course ID provided</div>;
	}

	return (
		<div className="min-h-screen bg-gray-50 dark:bg-gray-900">
			<MainHeader />

			<div className="max-w-4xl mx-auto px-4 py-8">
				{/* Header Actions */}
				<div className="flex items-center justify-between mb-6">
					<Button
						variant="outline"
						onClick={handleBack}
						className="flex items-center space-x-2"
					>
						<ArrowLeft className="h-4 w-4" />
						<span>Back to Home</span>
					</Button>

					<Button
						onClick={handleStartCourse}
						className="flex items-center space-x-2"
					>
						<BookOpen className="h-4 w-4" />
						<span>Start Course</span>
					</Button>
				</div>

				{/* Course Header */}
				<div className="bg-white dark:bg-gray-800 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700 p-6 mb-6">
					<h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100 mb-2">
						Course Preview
					</h1>
					<p className="text-gray-600 dark:text-gray-400">
						Course ID: {courseId}
					</p>
				</div>

				{/* Course Modules */}
				<div className="bg-white dark:bg-gray-800 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700 p-6">
					<h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-4">
						Course Modules
					</h2>
					<div className="text-center py-8 text-gray-500 dark:text-gray-400">
						<BookOpen className="h-12 w-12 mx-auto mb-4 opacity-50" />
						<p>Course preview functionality coming soon.</p>
					</div>
				</div>

				{/* Footer Actions */}
				<div className="mt-8 flex justify-center">
					<Button
						onClick={handleStartCourse}
						size="lg"
						className="flex items-center space-x-2 px-8"
					>
						<BookOpen className="h-5 w-5" />
						<span>Start Learning</span>
					</Button>
				</div>
			</div>
		</div>
	);
};

export default CoursePreviewPage;
