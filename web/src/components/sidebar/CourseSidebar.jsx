import { useMemo, useState } from "react"
import CompletionCheckbox from "@/components/sidebar/CompletionCheckbox"
import ExpandableSection from "@/components/sidebar/ExpandableSection"
import ProgressIndicator from "@/components/sidebar/ProgressIndicator"
import SidebarContainer from "@/components/sidebar/SidebarContainer"
import SidebarItem from "@/components/sidebar/SidebarItem"
import SidebarNav from "@/components/sidebar/SidebarNav"
import logger from "@/lib/logger"

/**
 * Course navigation sidebar that displays a hierarchical view of modules and lessons
 */
function CourseSidebar({
	modules = [],
	onLessonClick,
	onPracticeClick,
	activeLessonId = null,
	courseId,
	adaptiveEnabled = false,
	adaptiveProgressPct,
	frontierData,
	progressApi,
}) {
	const courseProgress = progressApi?.progress
	const toggleCompletion = progressApi?.toggleCompletion
	const isCompleted = progressApi?.isCompleted || (() => false)
	const updateProgressAsync = progressApi?.updateProgressAsync
	const metadata = progressApi?.metadata

	const [expandedModules, setExpandedModules] = useState(() => {
		return modules.length > 0 ? [modules[0].id] : []
	})

	const [practiceExpanded, setPracticeExpanded] = useState(true)
	const [readyExpanded, setReadyExpanded] = useState(true)

	const handleToggleModule = (moduleId) => {
		setExpandedModules((prev) => (prev.includes(moduleId) ? prev.filter((id) => id !== moduleId) : [...prev, moduleId]))
	}

	const progress =
		adaptiveEnabled && typeof adaptiveProgressPct === "number" ? adaptiveProgressPct : courseProgress?.percentage || 0

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

	const adaptiveLists = useMemo(() => {
		if (!adaptiveEnabled || !frontierData) {
			return { due: [], frontier: [] }
		}
		const listify = (arr) => (Array.isArray(arr) ? arr : [])
		const mapItem = (c) => {
			return {
				id: c.id,
				name: c.name,
				mastery: typeof c.mastery === "number" ? c.mastery : null,
			}
		}
		return {
			due: listify(frontierData.dueForReview).map((item) => mapItem(item)),
			frontier: listify(frontierData.frontier).map((item) => mapItem(item)),
		}
	}, [adaptiveEnabled, frontierData])

	const handleLessonCompletionToggle = async (lessonId) => {
		if (!lessonId) {
			return
		}

		if (!adaptiveEnabled) {
			if (toggleCompletion) {
				toggleCompletion(lessonId, totalLessons)
			}
			return
		}

		if (!updateProgressAsync) {
			return
		}

		const lessonIdStr = String(lessonId)
		const current = Array.isArray(metadata?.completedLessons) ? metadata.completedLessons : []
		const nextCompleted = current.includes(lessonIdStr)
			? current.filter((id) => id !== lessonIdStr)
			: [...current, lessonIdStr]

		try {
			await updateProgressAsync(courseProgress?.percentage ?? 0, {
				completed_lessons: nextCompleted,
				current_lesson_id: lessonIdStr,
				total_lessons: totalLessons,
			})
		} catch (error) {
			logger.error("Failed to update lesson completion", error, { courseId, lessonId: lessonIdStr })
		}
	}

	return (
		<SidebarContainer>
			<ProgressIndicator progress={progress} variant="course" />

			<SidebarNav>
				{adaptiveEnabled ? (
					<>
						<ExpandableSection
							key="practice-now"
							title="Practice Now"
							isExpanded={practiceExpanded}
							onToggle={() => setPracticeExpanded((v) => !v)}
							variant="course"
						>
							<ol>
								<SidebarItem
									key="practice-scheduled"
									title="Open scheduled session"
									isActive={false}
									isLocked={false}
									onClick={() => onPracticeClick?.()}
									variant="course"
								/>
								{adaptiveLists.due.map((item) => (
									<SidebarItem
										key={String(item.id)}
										title={item.name}
										isActive={false}
										isLocked={false}
										onClick={() => onPracticeClick?.(item.id)}
										variant="course"
										leftContent={
											<span className="inline-flex h-5 min-w-5 items-center justify-center rounded-full bg-amber-100 px-1.5 text-[10px] font-semibold text-amber-800">
												DUE
											</span>
										}
									/>
								))}
							</ol>
							{adaptiveLists.due.length === 0 ? (
								<p className="text-xs text-muted-foreground">No concepts are currently due.</p>
							) : null}
						</ExpandableSection>

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
										isActive={false}
										isLocked={false}
										onClick={() => onPracticeClick?.(item.id)}
										variant="course"
										leftContent={
											item.mastery === null ? null : (
												<div
													className="inline-flex"
													title="Confidence: predicted correctness now (based on recent answers and memory decay)"
												>
													<span className="inline-flex h-5 min-w-5 items-center justify-center rounded-full bg-emerald-100 px-1.5 text-[10px] font-semibold text-emerald-700">
														Conf {Math.round(item.mastery * 100)}%
													</span>
												</div>
											)
										}
									/>
								))}
							</ol>
						</ExpandableSection>
					</>
				) : (
					modules.map((module) => {
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
														onClick={() => handleLessonCompletionToggle(lesson.id)}
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
