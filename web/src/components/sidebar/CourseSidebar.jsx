import { useQuery } from "@tanstack/react-query"
import { useMemo, useState } from "react"
import { useCourseService } from "@/features/course/api/courseApi"
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
function CourseSidebar({
	modules = [],
	onLessonClick,
	activeLessonId = null,
	courseId,
	adaptiveEnabled = false,
	adaptiveProgressPct,
}) {
	const {
		progress: courseProgress,
		toggleCompletion,
		isCompleted,
		updateProgressAsync,
		metadata,
	} = useCourseProgress(courseId)
	const courseService = useCourseService(courseId)

	const [expandedModules, setExpandedModules] = useState(() => {
		return modules.length > 0 ? [modules[0].id] : []
	})

	// Adaptive section expansion state
	const [practiceExpanded, setPracticeExpanded] = useState(true)
	const [readyExpanded, setReadyExpanded] = useState(true)

	const handleToggleModule = (moduleId) => {
		setExpandedModules((prev) => (prev.includes(moduleId) ? prev.filter((id) => id !== moduleId) : [...prev, moduleId]))
	}

	const progress =
		adaptiveEnabled && typeof adaptiveProgressPct === "number" ? adaptiveProgressPct : courseProgress?.percentage || 0

	// Count total lessons across modules (including nested)
	const countLessons = (items = []) => {
		let total = 0
		for (const item of items) {
			total += 1
			if (Array.isArray(item?.lessons) && item.lessons.length > 0) {
				total += countLessons(item.lessons)
			}
		}
		return total
	}

	const totalLessons = (modules || []).reduce((sum, m) => sum + countLessons(m?.lessons || []), 0)

	// Adaptive sidebar data: due, frontier, coming soon
	const { data: frontierData } = useQuery({
		queryKey: ["course", courseId, "adaptive-concepts"],
		queryFn: async () => await courseService.fetchConceptFrontier(),
		enabled: Boolean(courseId) && adaptiveEnabled,
		staleTime: 30 * 1000,
		refetchOnWindowFocus: false,
	})

	const adaptiveLists = useMemo(() => {
		if (!adaptiveEnabled || !frontierData) {
			return { due: [], frontier: [] }
		}
		const listify = (arr) => (Array.isArray(arr) ? arr : [])
		const mapItem = (c) => {
			const lessonId = c.lessonIdRef || c.lesson_id_ref || c.lessonId || c.lesson_id
			return {
				id: c.id,
				name: c.name,
				description: c.description,
				lessonId,
				mastery: typeof c.mastery === "number" ? c.mastery : null,
				due: Boolean(c.nextReviewAt || c.next_review_at),
				locked: false,
			}
		}
		return {
			due: listify(frontierData.dueForReview).map(mapItem),
			frontier: listify(frontierData.frontier).map(mapItem),
		}
	}, [adaptiveEnabled, frontierData])

	return (
		<SidebarContainer>
			<ProgressIndicator progress={progress} variant="course" />

			<SidebarNav>
				{adaptiveEnabled ? (
					<>
						{adaptiveLists.due.length > 0 && (
							<ExpandableSection
								key="practice-now"
								title="Practice Now"
								isExpanded={practiceExpanded}
								onToggle={() => setPracticeExpanded((v) => !v)}
								variant="course"
							>
								<ol>
									{adaptiveLists.due.map((item) => (
										<SidebarItem
											key={String(item.id)}
											title={item.name}
											isActive={item.lessonId === activeLessonId}
											isLocked={false}
											onClick={() => onLessonClick?.(null, item.lessonId)}
											variant="course"
											leftContent={
												<span className="inline-flex h-5 min-w-5 items-center justify-center rounded-full bg-amber-100 px-1.5 text-[10px] font-semibold text-amber-800">
													DUE
												</span>
											}
										/>
									))}
								</ol>
							</ExpandableSection>
						)}

						<ExpandableSection
							key="ready-to-learn"
							title="Ready to Learn"
							isExpanded={readyExpanded}
							onToggle={() => setReadyExpanded((v) => !v)}
							variant="course"
						>
							<ol>
								{adaptiveLists.frontier.map((item) => (
									<SidebarItem
										key={String(item.id)}
										title={item.name}
										isActive={item.lessonId === activeLessonId}
										isLocked={false}
										onClick={() => onLessonClick?.(null, item.lessonId)}
										variant="course"
										leftContent={
											item.mastery !== null ? (
												/* Confidence badge with tooltip: predicted correctness now */
												<div className="inline-flex">
													<div title="Confidence: predicted correctness now (based on recent answers and memory decay)">
														<span className="inline-flex h-5 min-w-5 items-center justify-center rounded-full bg-emerald-100 px-1.5 text-[10px] font-semibold text-emerald-700">
															Conf {Math.round(item.mastery * 100)}%
														</span>
													</div>
												</div>
											) : null
										}
									/>
								))}
							</ol>
						</ExpandableSection>
					</>
				) : (
					modules.map((module, _index) => {
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
									{(module.lessons || []).map((lesson) => {
										return (
											<SidebarItem
												key={lesson.id}
												title={lesson.title}
												isActive={lesson.id === activeLessonId}
												isLocked={lesson.status === "locked"}
												onClick={() => onLessonClick?.(module.id, lesson.id)}
												variant="course"
												leftContent={
													<CompletionCheckbox
														isCompleted={isCompleted(lesson.id)}
														isLocked={lesson.status === "locked"}
														onClick={async () => {
															if (adaptiveEnabled) {
																const lessonIdStr = String(lesson.id)
																const current = Array.isArray(metadata?.completedLessons)
																	? metadata.completedLessons
																	: []
																const nextCompleted = current.includes(lessonIdStr)
																	? current.filter((id) => id !== lessonIdStr)
																	: [...current, lessonIdStr]
																try {
																	await updateProgressAsync(courseProgress?.percentage ?? 0, {
																		completed_lessons: nextCompleted,
																		current_lesson_id: lessonIdStr,
																		total_lessons: totalLessons,
																	})
																} catch (_e) {
																	// no-op: UI already reflects optimistic toggle
																}
															} else {
																toggleCompletion(lesson.id, totalLessons)
															}
														}}
														variant="course"
													/>
												}
											/>
										)
									})}
								</ol>
							</ExpandableSection>
						)
					})
				)}
			</SidebarNav>
		</SidebarContainer>
	)
}

export default CourseSidebar
