"use client"

import { CheckCircle, Lock } from "lucide-react"
import { useId, useLayoutEffect, useRef, useState } from "react"
import { useCourseProgress } from "@/features/course/hooks/use-course-progress"
import { cn } from "@/lib/utils"
import { useCourseNavigation } from "@/utils/navigationUtils"

// Helper function to find x position at given y coordinate on an SVG path
const xAtY = (path, targetY) => {
	const length = path.getTotalLength()
	let start = 0
	let end = length
	let bestX = 0

	// Binary search for closest point
	while (end - start > 0.1) {
		const mid = (start + end) / 2
		const point = path.getPointAtLength(mid)

		if (point.y > targetY) {
			end = mid
		} else {
			start = mid
			bestX = point.x
		}
	}

	return bestX
}

/**
 * TrackPath renders the vertical learning path visualization for a course.
 * @param {Object} props
 * @param {string} props.courseId - The ID of the course to display.
 * @param {Array} props.modules - The modules data passed from the parent component.
 * @returns {JSX.Element}
 */
export default function TrackPath({ courseId, modules = [], availableLessonIds }) {
	const pathId = useId()
	const titleId = useId()
	const descriptionId = useId()
	const { isCompleted } = useCourseProgress(courseId)
	const { goToLesson } = useCourseNavigation()

	// Handle lesson click - navigate to lesson page
	const handleLessonClick = (_moduleId, lessonId) => {
		if (!lessonId) {
			return
		}
		const useAdaptiveFlow = availableSet?.has(String(lessonId)) === true
		goToLesson(courseId, lessonId, useAdaptiveFlow ? { adaptiveFlow: true } : null)
	}

	// Create refs for path, wrappers, circles and lesson wrappers
	const svgRef = useRef(null)
	const wrapperRefs = useRef([])
	const circleRefs = useRef([])
	const wrapperRef = useRef(null)
	const lessonWrapRefs = useRef([])

	// Build single path
	const buildPath = (count) => {
		if (count <= 1) return "M50,0 L50,100" // Straight line for single module

		const segH = 100 / (count - 1)
		let d = "M50,0"
		for (let i = 0; i < count - 1; i++) {
			const y1 = i * segH
			const y2 = (i + 1) * segH
			const midY = (y1 + y2) / 2
			const xOff = i % 2 === 0 ? 20 : 80
			d += ` Q${xOff},${midY} 50,${y2}`
		}
		return d
	}

	// Track if initial positioning has been done
	const [initialPositioningDone, setInitialPositioningDone] = useState(false)
	// Refs to store calculated transforms
	const storedModuleTransforms = useRef([])
	const storedLessonTransforms = useRef([])

	// Effect for measuring and positioning circles using direct DOM manipulation
	useLayoutEffect(() => {
		// Skip further calculations if initial positioning is done
		// except on resize which needs recalculation
		const measure = (isInitialOrResize = false) => {
			if (!svgRef.current) return

			// Don't run measurements again unless it's initial or resize
			if (initialPositioningDone && !isInitialOrResize) return

			const svgBox = svgRef.current.getBoundingClientRect()
			const path = svgRef.current.querySelector(`[id="${pathId}"]`)
			if (!(path instanceof SVGPathElement)) return

			// modules
			for (let i = 0; i < wrapperRefs.current.length; i++) {
				const wrap = wrapperRefs.current[i]
				const circle = circleRefs.current[i]
				if (!wrap || !circle) continue

				// Use stored transform if available and not recalculating
				if (initialPositioningDone && !isInitialOrResize && storedModuleTransforms.current[i]) {
					wrap.style.transform = storedModuleTransforms.current[i]
					continue
				}

				wrap.style.transform = "none"
				const cBox = circle.getBoundingClientRect()
				const yPct = ((cBox.top + cBox.height / 2 - svgBox.top) / svgBox.height) * 100
				const xPct = xAtY(path, yPct)

				// Calculate the target position where the line is
				const target = svgBox.left + (xPct / 100) * svgBox.width
				// Calculate the current center of the circle
				const currentCenter = cBox.left + cBox.width / 2
				// Apply transform to move the circle so its center is on the line
				const transform = `translateX(${target - currentCenter}px)`
				wrap.style.transform = transform
				// Store the calculated transform
				storedModuleTransforms.current[i] = transform
			}

			// lessons
			for (let moduleIndex = 0; moduleIndex < lessonWrapRefs.current.length; moduleIndex++) {
				const wraps = lessonWrapRefs.current[moduleIndex] || []

				if (!storedLessonTransforms.current[moduleIndex]) {
					storedLessonTransforms.current[moduleIndex] = []
				}

				for (let lessonIndex = 0; lessonIndex < wraps.length; lessonIndex++) {
					const wrap = wraps[lessonIndex]
					if (!wrap) continue

					// Use stored transform if available and not recalculating
					if (
						initialPositioningDone &&
						!isInitialOrResize &&
						storedLessonTransforms.current[moduleIndex][lessonIndex]
					) {
						wrap.style.transform = storedLessonTransforms.current[moduleIndex][lessonIndex]
						continue
					}

					wrap.style.transform = "none"
					const box = wrap.getBoundingClientRect()
					const yPct = ((box.top + box.height / 2 - svgBox.top) / svgBox.height) * 100
					const xPct = xAtY(path, yPct)
					// Calculate the target position where the line is
					const target = svgBox.left + (xPct / 100) * svgBox.width
					// Calculate the current center of the lesson box
					const currentCenter = box.left + box.width / 2
					// Apply transform to move the lesson box so its center is on the line
					const transform = `translateX(${target - currentCenter}px)`
					wrap.style.transform = transform
					// Store the calculated transform
					storedLessonTransforms.current[moduleIndex][lessonIndex] = transform
				}
			}

			// Mark initial positioning as done after first calculation
			if (!initialPositioningDone) {
				setInitialPositioningDone(true)
			}
		}

		const scheduleMeasure = () => {
			requestAnimationFrame(() => measure(true))
		}

		// Run initial measurement
		scheduleMeasure()

		const ro = new ResizeObserver(() => scheduleMeasure())
		if (svgRef.current) {
			ro.observe(svgRef.current)
		}

		// Font loading might affect layout - apply initial positions when fonts are ready

		document.fonts?.ready.then(scheduleMeasure)

		// Handle resize with double RAF
		const handleResize = () => scheduleMeasure()
		window.addEventListener("resize", handleResize)

		return () => {
			ro.disconnect()
			window.removeEventListener("resize", handleResize)
		}
	}, [initialPositioningDone, pathId])

	// Note: Lesson viewing is handled by the nested CourseLayout via routing

	// Normalize available ids set for quick lookups (undefined => no locking)
	const availableSet = Array.isArray(availableLessonIds) ? new Set(availableLessonIds.map(String)) : null
	lessonWrapRefs.current = []

	return (
		<div key={`track-${modules.length}`} className="flex-1 min-h-screen flex flex-col p-4 md:p-6 lg:p-8">
			<div className="flex-1 max-w-2xl mx-auto w-full flex flex-col">
				{/* Duolingo-style vertical learning path */}
				<div className="flex-1 relative">
					{/* Central path - curved line */}
					<div className="absolute inset-0    z-0">
						<svg
							ref={svgRef}
							className="absolute size-full "
							preserveAspectRatio="none"
							viewBox="0 0 100 100"
							style={{ overflow: "visible" }}
							aria-label="Course progress path"
							role="img"
							aria-labelledby={`${titleId} ${descriptionId}`}
						>
							<title id={titleId}>Course progress path</title>
							<desc id={descriptionId}>A curved path showing course progression through modules</desc>
							<path
								id={pathId}
								d={buildPath(modules.length)}
								fill="none"
								stroke="var(--color-border)"
								strokeWidth="2"
								strokeLinecap="round"
							/>
						</svg>
					</div>

					{/* Modules and lessons */}
					<div
						ref={wrapperRef}
						className={cn(
							"relative z-10 pb-20 flex-1",
							!initialPositioningDone && "opacity-0",
							initialPositioningDone && "opacity-100 transition-opacity duration-300"
						)}
					>
						{modules.map((module, moduleIndex) => {
							const sortedLessons = Array.isArray(module.lessons)
								? module.lessons.toSorted((a, b) => a.order - b.order)
								: []
							const isModuleCompleted =
								module.status === "completed" ||
								(sortedLessons.length > 0 && sortedLessons.every((lesson) => isCompleted(lesson.id)))

							return (
								<div key={module.id} className="mb-16">
									{/* Module node with title beside it */}
									<div
										className="mb-12 relative flex justify-center"
										style={{
											marginLeft: "auto",
											marginRight: "auto",
											width: "fit-content",
										}}
									>
										<div
											ref={(el) => {
												wrapperRefs.current[moduleIndex] = el
											}}
											className={cn("flex items-center gap-6", moduleIndex % 2 === 0 ? "flex-row" : "flex-row-reverse")}
										>
											<div
												ref={(el) => {
													circleRefs.current[moduleIndex] = el
												}}
												className="relative shrink-0"
											>
												<div
													className={`size-24 rounded-full flex items-center justify-center shadow-lg ${
														isModuleCompleted ? "bg-completed" : "bg-muted"
													} ${moduleIndex % 2 === 0 ? "rotate-[-5deg]" : "rotate-[5deg]"}`}
												>
													<div className="absolute inset-2 flex items-center justify-center rounded-full bg-card">
														{isModuleCompleted ? (
															<CheckCircle className="size-10 text-completed" />
														) : (
															<div className="flex size-16 items-center justify-center rounded-full bg-muted text-2xl font-bold text-muted-foreground">
																{moduleIndex + 1}
															</div>
														)}
													</div>
												</div>
											</div>

											{((typeof module.title === "string" && module.title.trim()) ||
												(typeof module.description === "string" && module.description.trim())) && (
												<div
													className={cn(
														"relative max-w-[220px] min-w-[180px] pointer-events-none",
														moduleIndex % 2 === 0 ? "text-left" : "text-right"
													)}
												>
													{module.title ? (
														<h3 className="text-xl/snug font-bold text-foreground">{module.title}</h3>
													) : null}
													{module.description ? (
														<p className="mt-1 text-sm/tight text-muted-foreground">{module.description}</p>
													) : null}
												</div>
											)}
										</div>
									</div>

									{sortedLessons.length > 0 ? (
										<div className="relative mx-auto max-w-md">
											<div className="relative">
												{sortedLessons.map((lesson, lessonIndex) => {
													const completed = isCompleted(lesson.id)
													const locked = availableSet ? !completed && !availableSet.has(String(lesson.id)) : false
													let lessonCardStateClass =
														"border-border hover:border-border hover:bg-muted/30 hover:shadow-md"
													if (completed) {
														lessonCardStateClass = "border-completed/30 bg-completed/10"
													} else if (locked) {
														lessonCardStateClass = "border-paused/30 bg-muted/40 opacity-70"
													}

													return (
														<div
															key={lesson.id}
															className={cn("mb-4 flex", lessonIndex % 2 === 0 ? "justify-start" : "justify-end")}
														>
															<div
																className={cn(
																	"absolute top-1/2 z-0 h-0.5 bg-border",
																	lessonIndex % 2 === 0
																		? "left-1/2 right-[calc(100%-70px)]"
																		: "left-[calc(100%-70px)] right-1/2"
																)}
																style={{ top: `${lessonIndex * 84 + 40}px` }}
															/>

															<button
																type="button"
																ref={(el) => {
																	if (!lessonWrapRefs.current[moduleIndex]) lessonWrapRefs.current[moduleIndex] = []
																	lessonWrapRefs.current[moduleIndex][lessonIndex] = el
																}}
																className={cn(
																	"relative z-10 w-[calc(50%-20px)] rounded-xl border bg-card p-4 text-left shadow-sm",
																	lessonCardStateClass
																)}
																onClick={() => {
																	if (locked) return
																	handleLessonClick(module.id, lesson.id)
																}}
																aria-label={`Open lesson: ${lesson.title}`}
																aria-disabled={locked}
															>
																<div className="mb-2 flex items-center gap-3">
																	<div
																		className={cn(
																			"flex size-8 shrink-0 items-center justify-center rounded-full",
																			completed ? "bg-completed/10 text-completed" : "bg-muted text-muted-foreground"
																		)}
																	>
																		{completed ? (
																			<CheckCircle className="size-4" />
																		) : (
																			<span className="text-sm font-medium">{lessonIndex + 1}</span>
																		)}
																	</div>
																	<h4 className="text-sm font-medium text-foreground">{lesson.title}</h4>
																</div>
																<p className="ml-11 text-xs text-muted-foreground">{lesson.description}</p>

																{locked ? (
																	<span className="absolute right-2 top-2 inline-flex items-center justify-center rounded-md border border-paused/30 bg-muted/80 p-1">
																		<Lock className="size-3.5 text-paused" />
																	</span>
																) : null}
															</button>
														</div>
													)
												})}
											</div>
										</div>
									) : null}
								</div>
							)
						})}
					</div>
				</div>
			</div>
		</div>
	)
}
