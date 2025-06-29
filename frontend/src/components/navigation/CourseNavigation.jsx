/**
 * Course Navigation Component
 *
 * Provides navigation controls for moving between lessons within a course
 */

import { BookOpen, CheckCircle, ChevronLeft, ChevronRight } from "lucide-react";
import { useMemo } from "react";
import { useCourseNavigation } from "../../utils/navigationUtils";
import { Button } from "../ui/button";

/**
 * Calculate the next and previous lessons in a course
 * @param {Array} modules - Array of modules with lessons
 * @param {string} currentModuleId - Current module ID
 * @param {string} currentLessonId - Current lesson ID
 * @returns {Object} Navigation info with next/previous lessons
 */
function calculateLessonNavigation(modules, currentModuleId, currentLessonId) {
	if (!modules || modules.length === 0) {
		return { previous: null, next: null, current: null };
	}

	// Flatten all lessons across modules for linear navigation
	const allLessons = [];

	for (const module of modules) {
		if (module.lessons) {
			for (const lesson of module.lessons) {
				allLessons.push({
					...lesson,
					moduleId: module.id,
					moduleTitle: module.title,
				});
			}
		}
	}

	// Find current lesson index
	const currentIndex = allLessons.findIndex(
		(lesson) =>
			lesson.moduleId === currentModuleId && lesson.id === currentLessonId,
	);

	if (currentIndex === -1) {
		return { previous: null, next: null, current: null };
	}

	return {
		previous: currentIndex > 0 ? allLessons[currentIndex - 1] : null,
		next:
			currentIndex < allLessons.length - 1
				? allLessons[currentIndex + 1]
				: null,
		current: allLessons[currentIndex],
		currentIndex,
		totalLessons: allLessons.length,
	};
}

const CourseNavigation = ({
	courseId,
	currentModuleId,
	currentLessonId,
	modules = [],
	onLessonChange,
	showProgress = true,
	className = "",
}) => {
	const { goToLesson } = useCourseNavigation();

	const navigation = useMemo(
		() => calculateLessonNavigation(modules, currentModuleId, currentLessonId),
		[modules, currentModuleId, currentLessonId],
	);

	const handleNavigate = (lesson) => {
		if (!lesson) return;

		const newPath = `/course/${courseId}/module/${lesson.moduleId}/lesson/${lesson.id}`;

		// Call callback if provided
		if (onLessonChange) {
			onLessonChange(lesson, newPath);
		} else {
			// Default navigation
			goToLesson(courseId, lesson.moduleId, lesson.id);
		}
	};

	if (!navigation.current) {
		return null;
	}

	return (
		<div className={`flex items-center justify-between ${className}`}>
			{/* Previous Lesson */}
			<div className="flex-1">
				{navigation.previous ? (
					<Button
						variant="outline"
						onClick={() => handleNavigate(navigation.previous)}
						className="flex items-center space-x-2 max-w-[200px]"
					>
						<ChevronLeft className="h-4 w-4" />
						<div className="text-left truncate">
							<div className="text-xs text-gray-500">Previous</div>
							<div className="font-medium truncate">
								{navigation.previous.title || navigation.previous.slug}
							</div>
						</div>
					</Button>
				) : (
					<div /> // Empty div for spacing
				)}
			</div>

			{/* Progress Indicator */}
			{showProgress && (
				<div className="flex items-center space-x-2 px-4">
					<BookOpen className="h-4 w-4 text-gray-500" />
					<span className="text-sm text-gray-600 dark:text-gray-400">
						{navigation.currentIndex + 1} of {navigation.totalLessons}
					</span>
				</div>
			)}

			{/* Next Lesson */}
			<div className="flex-1 flex justify-end">
				{navigation.next ? (
					<Button
						variant="outline"
						onClick={() => handleNavigate(navigation.next)}
						className="flex items-center space-x-2 max-w-[200px]"
					>
						<div className="text-right truncate">
							<div className="text-xs text-gray-500">Next</div>
							<div className="font-medium truncate">
								{navigation.next.title || navigation.next.slug}
							</div>
						</div>
						<ChevronRight className="h-4 w-4" />
					</Button>
				) : (
					<div /> // Empty div for spacing
				)}
			</div>
		</div>
	);
};

// Compact version for lesson viewer
export const CompactCourseNavigation = ({
	courseId,
	currentModuleId,
	currentLessonId,
	modules,
	onLessonChange,
	className = "",
}) => {
	return (
		<CourseNavigation
			courseId={courseId}
			currentModuleId={currentModuleId}
			currentLessonId={currentLessonId}
			modules={modules}
			onLessonChange={onLessonChange}
			showProgress={false}
			className={`py-2 ${className}`}
		/>
	);
};

// Module navigation component for sidebar
export const ModuleNavigation = ({
	courseId,
	modules = [],
	currentModuleId,
	currentLessonId,
	onModuleClick,
	onLessonClick,
	className = "",
}) => {
	const { goToModule, goToLesson } = useCourseNavigation();

	const handleModuleClick = (module) => {
		if (onModuleClick) {
			onModuleClick(module);
		} else {
			goToModule(courseId, module.id);
		}
	};

	const handleLessonClick = (moduleId, lesson) => {
		if (onLessonClick) {
			onLessonClick(moduleId, lesson);
		} else {
			goToLesson(courseId, moduleId, lesson.id);
		}
	};

	return (
		<nav className={`space-y-2 ${className}`}>
			{modules.map((module, _moduleIndex) => (
				<div
					key={module.id}
					className="border border-gray-200 dark:border-gray-700 rounded-lg"
				>
					{/* Module Header */}
					<button
						onClick={() => handleModuleClick(module)}
						className={`w-full text-left p-3 rounded-t-lg border-b border-gray-200 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors ${
							currentModuleId === module.id
								? "bg-blue-50 dark:bg-blue-900/20 border-blue-200 dark:border-blue-800"
								: ""
						}`}
					>
						<div className="flex items-center justify-between">
							<div className="flex-1">
								<div className="font-medium text-gray-900 dark:text-gray-100">
									{module.title}
								</div>
								{module.description && (
									<div className="text-sm text-gray-600 dark:text-gray-400 mt-1">
										{module.description}
									</div>
								)}
							</div>
							{module.status === "completed" && (
								<CheckCircle className="h-5 w-5 text-green-500" />
							)}
						</div>
					</button>

					{/* Lessons List */}
					{module.lessons && module.lessons.length > 0 && (
						<div className="p-2 space-y-1">
							{module.lessons.map((lesson, _lessonIndex) => (
								<button
									key={lesson.id}
									onClick={() => handleLessonClick(module.id, lesson)}
									className={`w-full text-left p-2 rounded text-sm transition-colors ${
										currentModuleId === module.id &&
										currentLessonId === lesson.id
											? "bg-blue-100 dark:bg-blue-900/30 text-blue-900 dark:text-blue-100"
											: "hover:bg-gray-100 dark:hover:bg-gray-700 text-gray-700 dark:text-gray-300"
									}`}
								>
									<div className="flex items-center justify-between">
										<span className="truncate">
											{lesson.title || lesson.slug}
										</span>
										{lesson.status === "completed" && (
											<CheckCircle className="h-4 w-4 text-green-500 flex-shrink-0 ml-2" />
										)}
									</div>
								</button>
							))}
						</div>
					)}
				</div>
			))}
		</nav>
	);
};

export default CourseNavigation;
