import { useProgressSafe } from "@/hooks/useProgress";
import { useState } from "react";
import CompletionCheckbox from "./CompletionCheckbox";
import ExpandableSection from "./ExpandableSection";
import ProgressCircle from "./ProgressCircle";
import ProgressIndicator from "./ProgressIndicator";
import SidebarContainer from "./SidebarContainer";
import SidebarItem from "./SidebarItem";
import SidebarNav from "./SidebarNav";

/**
 * Course navigation sidebar that displays a hierarchical view of modules and lessons
 */
function CourseSidebar({
	modules = [],
	onLessonClick,
	activeLessonId = null,
	courseId,
}) {
	const { courseProgress, toggleLessonCompletion, isLessonCompleted } =
		useProgressSafe();

	const [expandedModules, setExpandedModules] = useState(() => {
		return modules.length > 0 ? [modules[0].id] : [];
	});

	const handleToggleModule = (moduleId) => {
		setExpandedModules((prev) =>
			prev.includes(moduleId)
				? prev.filter((id) => id !== moduleId)
				: [...prev, moduleId],
		);
	};

	const getModuleProgress = (module) => {
		if (!module.lessons || module.lessons.length === 0) return 0;
		const completedCount = module.lessons.filter((l) =>
			isLessonCompleted(l.id),
		).length;
		return (completedCount / module.lessons.length) * 100;
	};

	const progress = courseProgress?.progressPercentage || 0;

	return (
		<SidebarContainer>
			<ProgressIndicator progress={progress} variant="course" />

			<SidebarNav>
				{modules.map((module, index) => {
					const isExpanded = expandedModules.includes(module.id);
					const moduleProgress = getModuleProgress(module);

					return (
						<ExpandableSection
							key={module.id}
							title={module.title}
							isExpanded={isExpanded}
							onToggle={() => handleToggleModule(module.id)}
							variant="course"
							headerContent={
								<ProgressCircle
									number={index + 1}
									progress={moduleProgress}
									variant="course"
								/>
							}
						>
							<ol>
								{(module.lessons || []).map((lesson) => (
									<SidebarItem
										key={lesson.id}
										title={lesson.title}
										isActive={lesson.id === activeLessonId}
										isCompleted={isLessonCompleted(lesson.id)}
										isLocked={lesson.status === "locked"}
										onClick={() => onLessonClick?.(module.id, lesson.id)}
										variant="course"
										leftContent={
											<CompletionCheckbox
												isCompleted={isLessonCompleted(lesson.id)}
												isLocked={lesson.status === "locked"}
												onClick={() => toggleLessonCompletion(lesson.id, module.id)}
												variant="course"
											/>
										}
									/>
								))}
							</ol>
						</ExpandableSection>
					);
				})}
			</SidebarNav>
		</SidebarContainer>
	);
}

export default CourseSidebar;
