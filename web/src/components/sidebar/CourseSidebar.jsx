import { useState } from "react"
import { useCourseProgress } from "@/features/course/hooks/useCourseProgress"
import CompletionCheckbox from "./CompletionCheckbox"
import ExpandableSection from "./ExpandableSection"

import ProgressIndicator from "./ProgressIndicator"
import SidebarContainer from "./SidebarContainer"
import SidebarItem from "./SidebarItem"
import SidebarNav from "./SidebarNav"

/**
 * Course navigation sidebar that displays a hierarchical view of modules and lessons
 */
function CourseSidebar({ modules = [], onLessonClick, activeLessonId = null, courseId }) {
	const { progress: courseProgress, toggleCompletion, isCompleted } = useCourseProgress(courseId)

	const [expandedModules, setExpandedModules] = useState(() => {
		return modules.length > 0 ? [modules[0].id] : []
	})

	const handleToggleModule = (moduleId) => {
		setExpandedModules((prev) => (prev.includes(moduleId) ? prev.filter((id) => id !== moduleId) : [...prev, moduleId]))
	}

	const progress = courseProgress?.percentage || 0

	return (
		<SidebarContainer>
			<ProgressIndicator progress={progress} variant="course" />

			<SidebarNav>
				{modules.map((module, _index) => {
					const isExpanded = expandedModules.includes(module.id)

					return (
						<ExpandableSection
							key={module.id}
							title={module.title}
							isExpanded={isExpanded}
							onToggle={() => handleToggleModule(module.id)}
							variant="course"
						>
							<ol>
								{(module.lessons || []).map((lesson) => (
									<SidebarItem
										key={lesson.id}
										title={lesson.title}
										isActive={lesson.id === activeLessonId}
										isCompleted={isCompleted(lesson.id)}
										isLocked={lesson.status === "locked"}
										onClick={() => onLessonClick?.(module.id, lesson.id)}
										variant="course"
										leftContent={
											<CompletionCheckbox
												isCompleted={isCompleted(lesson.id)}
												isLocked={lesson.status === "locked"}
												onClick={() => toggleCompletion(lesson.id)}
												variant="course"
											/>
										}
									/>
								))}
							</ol>
						</ExpandableSection>
					)
				})}
			</SidebarNav>
		</SidebarContainer>
	)
}

export default CourseSidebar
