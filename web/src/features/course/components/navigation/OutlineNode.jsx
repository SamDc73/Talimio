import { CheckCircle, ChevronRight, Circle } from "lucide-react"
import { useState } from "react"

const cn = (...classes) => classes.filter(Boolean).join(" ")

/**
 * @param {Object} props
 * @param {Object} props.module - The module object (with lessons)
 * @param {number} props.index - The module index (for numbering)
 * @param {Function} [props.onLessonClick] - Optional handler for lesson click
 * @param {Function} [props.isLessonCompleted] - Function to check if a lesson is completed
 * @param {Function} [props.toggleLessonCompletion] - Function to toggle lesson completion status
 * @returns {JSX.Element}
 */
function OutlineNode({ module, index, onLessonClick, isLessonCompleted, toggleLessonCompletion }) {
	const moduleId = module.id ?? index + 1
	const [expanded, setExpanded] = useState(index === 0) // First module expanded by default

	const isItemCompleted = (item) => {
		return isLessonCompleted?.(item.id) || item.status === "completed"
	}

	const processNestedLessons = (item, counts) => {
		if (!Array.isArray(item.lessons) || item.lessons.length === 0) {
			return counts
		}

		const [subTotal, subCompleted] = countLessons(item.lessons)
		counts.total += subTotal
		counts.completed += subCompleted
		return counts
	}

	const countLessons = (items) => {
		const counts = { total: 0, completed: 0 }

		if (!items || !items.length) {
			return [counts.total, counts.completed]
		}

		for (const item of items) {
			if (!item || typeof item.title !== "string") continue

			counts.total += 1
			if (isItemCompleted(item)) {
				counts.completed += 1
			}

			processNestedLessons(item, counts)
		}

		return [counts.total, counts.completed]
	}

	const [totalLessons, completedLessons] = countLessons(module.lessons || [])
	const progress = totalLessons > 0 ? (completedLessons / totalLessons) * 100 : 0
	const isModuleCompleted = progress === 100 && totalLessons > 0

	function LessonStatusIndicator({ isCompleted, indexStr: _indexStr }) {
		// Show a proper empty circle when not completed to match the old outline's spirit
		if (isCompleted) {
			return <CheckCircle className="w-5 h-5 text-emerald-600 shrink-0" />
		}
		return <Circle className="w-5 h-5 text-zinc-400 shrink-0" />
	}

	// Removed the separate action button; the whole row is clickable now with a subtle chevron indicator

	function LessonContent({ lesson, isCompleted, currentLessonIndexStr, idx, onLessonClick }) {
		const containerClasses = cn(
			"group flex items-center gap-3 rounded-2xl border border-transparent px-4 py-3 md:px-5 md:py-3.5 transition-colors",
			isCompleted ? "border-emerald-200 bg-emerald-50/80" : "hover:border-emerald-200 hover:bg-emerald-50/40"
		)
		const titleClasses = cn("truncate text-sm font-medium", isCompleted ? "text-muted-foreground" : "text-foreground")

		return (
			<div className={containerClasses}>
				<button
					type="button"
					onClick={() => toggleLessonCompletion?.(lesson.id)}
					className="rounded-full border border-transparent p-0.5 transition-transform hover:scale-105 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400 focus-visible:ring-offset-2"
					aria-label={isCompleted ? "Mark as incomplete" : "Mark as complete"}
				>
					<LessonStatusIndicator isCompleted={isCompleted} indexStr={currentLessonIndexStr} />
				</button>
				<button
					type="button"
					onClick={() => onLessonClick?.(idx, lesson.id)}
					className="flex min-w-0 flex-1 items-center justify-between gap-3 rounded-xl px-2 py-1 text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400 focus-visible:ring-offset-2"
				>
					<span className={titleClasses}>{lesson.title}</span>
					<ChevronRight className="h-4 w-4 text-muted-foreground/60 opacity-0 transition-opacity group-hover:opacity-100" />
				</button>
			</div>
		)
	}

	function LessonItem({ lesson, idx, depth, parentIndexStr, onLessonClick, moduleId }) {
		const currentLessonIndexStr = parentIndexStr ? `${parentIndexStr}.${idx + 1}` : `${idx + 1}`
		const isCompleted = isItemCompleted(lesson)
		const lessonKey = lesson.id ?? `${moduleId}-lesson-${depth}-${idx}`
		const hasNestedLessons = lesson.lessons?.length > 0
		const depthClass = depth > 0 ? "ml-5 mt-3 border-l border-emerald-100/60 pl-4 pt-3" : "mt-3"

		return (
			<div key={lessonKey} className={`space-y-2.5 ${depthClass}`}>
				<LessonContent
					lesson={lesson}
					isCompleted={isCompleted}
					currentLessonIndexStr={currentLessonIndexStr}
					idx={idx}
					onLessonClick={onLessonClick}
				/>

				{hasNestedLessons && (
					<LessonList
						lessons={lesson.lessons}
						depth={depth + 1}
						parentIndexStr={currentLessonIndexStr}
						onLessonClick={onLessonClick}
						moduleId={moduleId}
					/>
				)}
			</div>
		)
	}

	function LessonList({ lessons, depth = 0, parentIndexStr = "", onLessonClick, moduleId }) {
		return (
			<>
				{(lessons || []).map((lesson, idx) => (
					<LessonItem
						key={lesson.id ?? `${moduleId}-lesson-${depth}-${idx}`}
						lesson={lesson}
						idx={idx}
						depth={depth}
						parentIndexStr={parentIndexStr}
						onLessonClick={onLessonClick}
						moduleId={moduleId}
					/>
				))}
			</>
		)
	}

	return (
		<div className="relative overflow-hidden rounded-3xl border border-border/70 bg-card/95 p-5 md:p-6 lg:p-7 shadow-sm transition-shadow hover:shadow-md">
			<button
				type="button"
				className="mb-5 flex w-full items-center gap-3 text-left md:gap-4"
				onClick={() => setExpanded((e) => !e)}
				aria-expanded={expanded}
				aria-controls={`module-content-${moduleId}`}
			>
				<div
					className={cn(
						"flex h-8 w-8 shrink-0 items-center justify-center rounded-full border text-sm font-medium transition-all duration-300",
						isModuleCompleted
							? "border-emerald-300 bg-emerald-50 text-emerald-700"
							: "border-border/70 bg-muted/60 text-muted-foreground"
					)}
				>
					{isModuleCompleted ? <CheckCircle className="h-4 w-4" /> : index + 1}
				</div>

				<h2 className="flex-1 truncate text-lg font-semibold text-foreground md:text-xl" title={module.title}>
					{module.title}
				</h2>
				{isModuleCompleted && (
					<span className="ml-auto rounded-full border border-emerald-200 bg-emerald-50 px-2.5 py-0.5 text-xs font-semibold text-emerald-700">
						Completed
					</span>
				)}
			</button>

			<div className="mb-5 flex flex-wrap items-center gap-3 text-xs text-muted-foreground">
				<div>
					{completedLessons} of {totalLessons} lessons completed
				</div>
				<div className="relative h-1.5 flex-1 overflow-hidden rounded-full bg-muted/40 md:h-2">
					<div
						className="h-full rounded-full bg-emerald-500 transition-all duration-500"
						style={{ width: `${progress}%` }}
					/>
				</div>
			</div>

			<div
				id={`module-content-${moduleId}`}
				className={cn(
					"overflow-hidden transition-all duration-300 ease-in-out",
					expanded ? "max-h-[1000px] opacity-100" : "max-h-0 opacity-0"
				)}
				style={{ transitionProperty: "max-height, opacity" }}
			>
				{expanded && (
					<div className="space-y-2.5">
						<LessonList lessons={module.lessons || []} onLessonClick={onLessonClick} moduleId={module.id} />
					</div>
				)}
			</div>
		</div>
	)
}

export default OutlineNode
