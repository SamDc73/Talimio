"use client";

import { CheckCircle } from "lucide-react";
import { useLayoutEffect, useRef, useState } from "react";
import { cn } from "@/lib/utils";
import { useProgress } from "../../../../hooks/useProgress";
import { useCourseNavigation } from "../../../../utils/navigationUtils";

// Helper function to find x position at given y coordinate on an SVG path
const xAtY = (path, targetY) => {
	const length = path.getTotalLength();
	let start = 0;
	let end = length;
	let bestX = 0;

	// Binary search for closest point
	while (end - start > 0.1) {
		const mid = (start + end) / 2;
		const point = path.getPointAtLength(mid);

		if (point.y > targetY) {
			end = mid;
		} else {
			start = mid;
			bestX = point.x;
		}
	}

	return bestX;
};

/**
 * TrackView renders a vertical learning path visualization of the roadmap
 * @param {Object} props
 * @param {string} props.roadmapId - The ID of the roadmap to display.
 * @param {Array} props.modules - The modules data passed from parent component.
 * @returns {JSX.Element}
 */
export default function TrackView({ roadmapId, modules = [] }) {
	const { courseProgress, isLessonCompleted } = useProgress();
	const { goToLesson } = useCourseNavigation();

	// Handle lesson click - navigate to lesson page
	const handleLessonClick = async (
		_moduleId,
		lessonId,
		_lessonTitle,
		_lessonDescription,
	) => {
		try {
			// Navigate to the lesson using the course page
			goToLesson(roadmapId, lessonId);
		} catch (err) {
			console.error("Error navigating to lesson:", err);
		}
	};

	// Create refs for path, wrappers, circles and lesson wrappers
	const svgRef = useRef(null);
	const wrapperRefs = useRef([]);
	const circleRefs = useRef([]);
	const wrapperRef = useRef(null);
	const lessonWrapRefs = useRef([]);

	// Build single path
	const buildPath = (count) => {
		if (count <= 1) return "M50,0 L50,100"; // Straight line for single module

		const segH = 100 / (count - 1);
		let d = "M50,0";
		for (let i = 0; i < count - 1; i++) {
			const y1 = i * segH;
			const y2 = (i + 1) * segH;
			const midY = (y1 + y2) / 2;
			const xOff = i % 2 === 0 ? 20 : 80;
			d += ` Q${xOff},${midY} 50,${y2}`;
		}
		return d;
	};

	// Track if initial positioning has been done
	const [initialPositioningDone, setInitialPositioningDone] = useState(false);
	// Refs to store calculated transforms
	const storedModuleTransforms = useRef([]);
	const storedLessonTransforms = useRef([]);

	// Effect for measuring and positioning circles using direct DOM manipulation
	useLayoutEffect(() => {
		// Skip further calculations if initial positioning is done
		// except on resize which needs recalculation
		const measure = (isInitialOrResize = false) => {
			if (!svgRef.current) return;

			// Don't run measurements again unless it's initial or resize
			if (initialPositioningDone && !isInitialOrResize) return;

			const svgBox = svgRef.current.getBoundingClientRect();
			const path = svgRef.current.querySelector("#coursePath");
			if (!(path instanceof SVGPathElement)) return;

			// modules
			for (let i = 0; i < wrapperRefs.current.length; i++) {
				const wrap = wrapperRefs.current[i];
				const circle = circleRefs.current[i];
				if (!wrap || !circle) continue;

				// Use stored transform if available and not recalculating
				if (
					initialPositioningDone &&
					!isInitialOrResize &&
					storedModuleTransforms.current[i]
				) {
					wrap.style.transform = storedModuleTransforms.current[i];
					continue;
				}

				wrap.style.transform = "none";
				const cBox = circle.getBoundingClientRect();
				const yPct =
					((cBox.top + cBox.height / 2 - svgBox.top) / svgBox.height) * 100;
				const xPct = xAtY(path, yPct);

				// Calculate the target position where the line is
				const target = svgBox.left + (xPct / 100) * svgBox.width;
				// Calculate the current center of the circle
				const currentCenter = cBox.left + cBox.width / 2;
				// Apply transform to move the circle so its center is on the line
				const transform = `translateX(${target - currentCenter}px)`;
				wrap.style.transform = transform;
				// Store the calculated transform
				storedModuleTransforms.current[i] = transform;
			}

			// lessons
			for (
				let moduleIndex = 0;
				moduleIndex < lessonWrapRefs.current.length;
				moduleIndex++
			) {
				const wraps = lessonWrapRefs.current[moduleIndex] || [];

				if (!storedLessonTransforms.current[moduleIndex]) {
					storedLessonTransforms.current[moduleIndex] = [];
				}

				for (let lessonIndex = 0; lessonIndex < wraps.length; lessonIndex++) {
					const wrap = wraps[lessonIndex];
					if (!wrap) continue;

					// Use stored transform if available and not recalculating
					if (
						initialPositioningDone &&
						!isInitialOrResize &&
						storedLessonTransforms.current[moduleIndex][lessonIndex]
					) {
						wrap.style.transform =
							storedLessonTransforms.current[moduleIndex][lessonIndex];
						continue;
					}

					wrap.style.transform = "none";
					const box = wrap.getBoundingClientRect();
					const yPct =
						((box.top + box.height / 2 - svgBox.top) / svgBox.height) * 100;
					const xPct = xAtY(path, yPct);
					// Calculate the target position where the line is
					const target = svgBox.left + (xPct / 100) * svgBox.width;
					// Calculate the current center of the lesson box
					const currentCenter = box.left + box.width / 2;
					// Apply transform to move the lesson box so its center is on the line
					const transform = `translateX(${target - currentCenter}px)`;
					wrap.style.transform = transform;
					// Store the calculated transform
					storedLessonTransforms.current[moduleIndex][lessonIndex] = transform;
				}
			}

			// Mark initial positioning as done after first calculation
			if (!initialPositioningDone) {
				setInitialPositioningDone(true);
			}
		};

		// Run initial measurement
		requestAnimationFrame(() => requestAnimationFrame(() => measure(true)));

		const ro = new ResizeObserver(() =>
			requestAnimationFrame(() => requestAnimationFrame(() => measure(true))),
		);
		if (svgRef.current) {
			ro.observe(svgRef.current);
		}

		// Font loading might affect layout - apply initial positions when fonts are ready
		document.fonts?.ready.then(() => {
			requestAnimationFrame(() => requestAnimationFrame(() => measure(true)));
		});

		// Handle resize with double RAF
		const handleResize = () =>
			requestAnimationFrame(() => requestAnimationFrame(() => measure(true)));
		window.addEventListener("resize", handleResize);

		return () => {
			ro.disconnect();
			window.removeEventListener("resize", handleResize);
		};
	}, [initialPositioningDone]); // Add modules as dependency to trigger recalculation when data changes

	// Handle empty state

	if (!modules || modules.length === 0) {
		return (
			<div className="flex-1 min-h-screen flex flex-col items-center justify-center text-zinc-500">
				<p>No track content available for this roadmap.</p>
			</div>
		);
	}

	// Note: Lesson viewing is now handled by CoursePage via navigation

	return (
		<div className="flex-1 min-h-screen flex flex-col p-4 md:p-6 lg:p-8">
			<div className="flex-1 max-w-2xl mx-auto w-full flex flex-col">
				{/* Duolingo-style vertical learning path */}
				<div className="flex-1 relative">
					{/* Central path - curved line */}
					<div className="absolute left-0 right-0 top-0 bottom-0 z-0">
						<svg
							ref={svgRef}
							className="absolute w-full h-full"
							preserveAspectRatio="none"
							viewBox="0 0 100 100"
							style={{ overflow: "visible" }}
							aria-label="Course progress path"
							role="img"
							aria-labelledby="course-path-title course-path-desc"
						>
							<title id="course-path-title">Course progress path</title>
							<desc id="course-path-desc">
								A curved path showing course progression through modules
							</desc>
							<path
								id="coursePath"
								d={buildPath(modules.length)}
								fill="none"
								stroke="#10b981"
								strokeWidth="2"
								strokeLinecap="round"
								className="path"
							/>
						</svg>
					</div>

					{/* Modules and lessons */}
					<div
						ref={wrapperRef}
						className={cn(
							"relative z-10 pb-20 flex-1",
							!initialPositioningDone && "opacity-0",
							initialPositioningDone &&
								"opacity-100 transition-opacity duration-300",
						)}
					>
						{/* Clear lesson refs before mapping */}
						{(() => {
							lessonWrapRefs.current = [];
							return null;
						})()}
						{modules.map((module, moduleIndex) => (
							<div key={module.id} className="mb-16">
								{/* Module node with title beside it */}
								<div
									className="relative flex justify-center mb-12"
									style={{
										marginLeft: "auto",
										marginRight: "auto",
										width: "fit-content",
									}}
								>
									<div
										ref={(el) => {
											wrapperRefs.current[moduleIndex] = el;
										}}
										className={cn(
											"flex items-center gap-6",
											moduleIndex % 2 === 0 ? "flex-row" : "flex-row-reverse",
										)}
									>
										{/* Module circle */}
										<div
											ref={(el) => {
												circleRefs.current[moduleIndex] = el;
											}}
											className="relative shrink-0"
										>
											<div
												className={`w-24 h-24 rounded-full bg-emerald-500 flex items-center justify-center shadow-lg ${
													moduleIndex % 2 === 0
														? "rotate-[-5deg]"
														: "rotate-[5deg]"
												}`}
											>
												<div className="absolute inset-2 rounded-full bg-white flex items-center justify-center">
													{module.status === "completed" ? (
														<CheckCircle className="w-10 h-10 text-emerald-500" />
													) : (
														<div className="w-16 h-16 rounded-full flex items-center justify-center text-2xl font-bold text-emerald-600 bg-emerald-50">
															{moduleIndex + 1}
														</div>
													)}
												</div>
											</div>
										</div>

										{/* Module title */}
										<div
											className={cn(
												"relative max-w-[220px] min-w-[180px] pointer-events-none",
												moduleIndex % 2 === 0 ? "text-left" : "text-right",
											)}
										>
											<h3 className="text-xl font-bold text-slate-800 leading-snug">
												{module.title}
											</h3>
											<p className="text-slate-500 text-sm mt-1 leading-tight">
												{module.description}
											</p>
										</div>
									</div>
								</div>

								{/* Lessons - always shown */}
								{module.lessons && module.lessons.length > 0 && (
									<div className="relative mx-auto max-w-md">
										{/* Lessons container with alternating sides */}
										<div className="relative">
											{module.lessons
												.sort((a, b) => a.order - b.order)
												.map((lesson, lessonIndex) => (
													<div
														key={lesson.id}
														className={cn(
															"mb-4 flex",
															lessonIndex % 2 === 0
																? "justify-start"
																: "justify-end",
														)}
													>
														{/* Connector line to center path */}
														<div
															className={cn(
																"absolute top-1/2 h-0.5 bg-emerald-200 z-0",
																lessonIndex % 2 === 0
																	? "left-1/2 right-[calc(100%-70px)]"
																	: "right-1/2 left-[calc(100%-70px)]",
															)}
															style={{ top: `${lessonIndex * 84 + 40}px` }}
														/>

														{/* Lesson card */}
														<button
															type="button"
															ref={(el) => {
																if (!lessonWrapRefs.current[moduleIndex])
																	lessonWrapRefs.current[moduleIndex] = [];
																lessonWrapRefs.current[moduleIndex][
																	lessonIndex
																] = el;
															}}
															className={cn(
																"relative bg-white border rounded-xl p-4 shadow-sm w-[calc(50%-20px)] hover:shadow-md hover:border-emerald-300 z-10 text-left",
																isLessonCompleted(lesson.id)
																	? "border-emerald-300 bg-emerald-50/30"
																	: "border-slate-200",
															)}
															onClick={() =>
																handleLessonClick(
																	module.id,
																	lesson.id,
																	lesson.title,
																	lesson.description,
																)
															}
															aria-label={`Open lesson: ${lesson.title}`}
														>
															<div className="flex items-center gap-3 mb-2">
																<div
																	className={cn(
																		"w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0",
																		isLessonCompleted(lesson.id)
																			? "bg-emerald-100 text-emerald-600"
																			: "bg-slate-100 text-slate-600",
																	)}
																>
																	{isLessonCompleted(lesson.id) ? (
																		<CheckCircle className="w-4 h-4" />
																	) : (
																		<span className="text-sm font-medium">
																			{lessonIndex + 1}
																		</span>
																	)}
																</div>
																<h4 className="font-medium text-slate-800 text-sm">
																	{lesson.title}
																</h4>
															</div>
															<p className="text-xs text-slate-500 ml-11">
																{lesson.description}
															</p>
														</button>
													</div>
												))}
										</div>
									</div>
								)}
							</div>
						))}
					</div>
				</div>
			</div>
		</div>
	);
}
