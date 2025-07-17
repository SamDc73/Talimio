import { ArrowRight, CheckCircle } from "lucide-react";
import { useState } from "react";

const cn = (...classes) => classes.filter(Boolean).join(" ");

/**
 * @param {Object} props
 * @param {Object} props.module - The module object (with lessons)
 * @param {number} props.index - The module index (for numbering)
 * @param {Function} [props.onLessonClick] - Optional handler for lesson click
 * @param {Function} [props.isLessonCompleted] - Function to check if a lesson is completed
 * @param {Function} [props.toggleLessonCompletion] - Function to toggle lesson completion status
 * @returns {JSX.Element}
 */
function OutlineNode({
	module,
	index,
	onLessonClick,
	isLessonCompleted,
	toggleLessonCompletion,
}) {
	const moduleId = module.id ?? index + 1;
	const [expanded, setExpanded] = useState(index === 0); // First module expanded by default

	const isItemCompleted = (item) => {
		return (
			isLessonCompleted?.(item.id) ||
			item.status === "completed"
		);
	};

	const processNestedLessons = (item, counts) => {
		if (!Array.isArray(item.lessons) || item.lessons.length === 0) {
			return counts;
		}

		const [subTotal, subCompleted] = countLessons(item.lessons);
		counts.total += subTotal;
		counts.completed += subCompleted;
		return counts;
	};

	const countLessons = (items) => {
		const counts = { total: 0, completed: 0 };

		if (!items || !items.length) {
			return [counts.total, counts.completed];
		}

		for (const item of items) {
			if (!item || typeof item.title !== "string") continue;

			counts.total += 1;
			if (isItemCompleted(item)) {
				counts.completed += 1;
			}

			processNestedLessons(item, counts);
		}

		return [counts.total, counts.completed];
	};

	const [totalLessons, completedLessons] = countLessons(module.lessons || []);
	const progress =
		totalLessons > 0 ? (completedLessons / totalLessons) * 100 : 0;
	const isModuleCompleted = progress === 100 && totalLessons > 0;

	const LessonStatusIndicator = ({ isCompleted, indexStr }) => {
		if (isCompleted) {
			return <CheckCircle className="w-5 h-5 text-emerald-600 shrink-0" />;
		}

		return (
			<div
				className={cn(
					"flex items-center justify-center w-5 h-5 rounded-full text-xs font-medium shrink-0",
					"bg-zinc-100 text-zinc-700",
				)}
			>
				{indexStr}
			</div>
		);
	};

	const LessonActionButton = ({ isCompleted, onClick }) => {
		const buttonStyle = isCompleted
			? "text-white bg-emerald-500 hover:bg-emerald-600"
			: "text-emerald-700 bg-emerald-100 hover:bg-emerald-200";

		return (
			<button
				type="button"
				onClick={(e) => {
					e.preventDefault();
					e.stopPropagation();
					if (onClick) {
						onClick();
					}
				}}
				className={cn(
					"flex items-center gap-1 px-3 py-1.5 text-sm font-medium transition-colors rounded-md shrink-0 ml-2",
					buttonStyle,
				)}
			>
				{isCompleted ? "View" : "Start"}
				<ArrowRight className="w-4 h-4" />
			</button>
		);
	};

	const LessonContent = ({
		lesson,
		isCompleted,
		currentLessonIndexStr,
		idx,
		onLessonClick,
		moduleId,
	}) => {
		return (
			<div
				className={cn(
					"flex items-center justify-between p-4 transition-all border rounded-lg",
					isCompleted
						? "bg-emerald-50 border-emerald-100"
						: "bg-white border-zinc-200 hover:border-emerald-200 hover:bg-emerald-50/30",
				)}
			>
				<div className="flex items-center gap-3 flex-1 min-w-0">
					<button
						type="button"
						onClick={(e) => {
							e.preventDefault();
							e.stopPropagation();
							if (toggleLessonCompletion) {
								toggleLessonCompletion(lesson.id, moduleId);
							}
						}}
						className="transition-transform hover:scale-110 focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:ring-offset-2 rounded-full"
						aria-label={isCompleted ? "Mark as incomplete" : "Mark as complete"}
					>
						<LessonStatusIndicator
							isCompleted={isCompleted}
							indexStr={currentLessonIndexStr}
						/>
					</button>
					<div className="flex flex-col min-w-0">
						<span className={cn("font-medium truncate", "text-zinc-800")}>
							{lesson.title}
						</span>
						{lesson.description && (
							<span className="text-sm text-zinc-500 truncate">
								{lesson.description}
							</span>
						)}
					</div>
				</div>
				<LessonActionButton
					isCompleted={isCompleted}
					onClick={() => {
						onLessonClick?.(idx, lesson.id);
					}}
				/>
			</div>
		);
	};

	const LessonItem = ({
		lesson,
		idx,
		depth,
		parentIndexStr,
		onLessonClick,
		moduleId,
	}) => {
		const currentLessonIndexStr = parentIndexStr
			? `${parentIndexStr}.${idx + 1}`
			: `${idx + 1}`;
		const isCompleted = isItemCompleted(lesson);
		const lessonKey = lesson.id ?? `${moduleId}-lesson-${depth}-${idx}`;
		const hasNestedLessons = lesson.lessons?.length > 0;
		const depthClass =
			depth > 0
				? "ml-6 mt-3 border-l-2 border-emerald-100/50 pl-4 pt-3"
				: "mt-3";

		return (
			<div key={lessonKey} className={`space-y-3 ${depthClass}`}>
				<LessonContent
					lesson={lesson}
					isCompleted={isCompleted}
					currentLessonIndexStr={currentLessonIndexStr}
					idx={idx}
					onLessonClick={onLessonClick}
					moduleId={moduleId}
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
		);
	};

	const LessonList = ({
		lessons,
		depth = 0,
		parentIndexStr = "",
		onLessonClick,
		moduleId,
	}) => {
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
		);
	};

	return (
		<div className="p-6 mb-8 bg-white border border-zinc-200 rounded-xl shadow-sm hover:shadow-md transition-shadow relative overflow-hidden">
			<button
				type="button"
				className="flex items-center gap-2 mb-4 w-full text-left"
				onClick={() => setExpanded((e) => !e)}
				aria-expanded={expanded}
				aria-controls={`module-content-${moduleId}`}
			>
				<div
					className={cn(
						"flex items-center justify-center w-7 h-7 rounded-full text-xs font-medium transition-all duration-300 shrink-0",
						isModuleCompleted
							? "bg-emerald-500 text-white hover:bg-emerald-600"
							: "bg-zinc-100 text-zinc-700",
					)}
				>
					{isModuleCompleted ? <CheckCircle className="w-4 h-4" /> : index + 1}
				</div>

				<h2
					className="text-xl font-semibold text-zinc-900 flex-1 truncate"
					title={module.title}
				>
					{module.title}
				</h2>
				{isModuleCompleted && (
					<span className="ml-auto px-2 py-0.5 text-xs font-medium bg-emerald-100 text-emerald-800 rounded-full shrink-0">
						Completed
					</span>
				)}
			</button>

			<div className="flex items-center gap-2 mb-4">
				<div className="text-xs text-zinc-500">
					{completedLessons} of {totalLessons} lessons completed
				</div>
				<div className="flex-1 h-1.5 bg-zinc-100 rounded-full overflow-hidden">
					<div
						className="h-full bg-emerald-500 rounded-full transition-all duration-500"
						style={{ width: `${progress}%` }}
					/>
				</div>
			</div>

			<div
				id={`module-content-${moduleId}`}
				className={cn(
					"transition-all duration-300 ease-in-out overflow-hidden",
					expanded ? "max-h-[1000px] opacity-100" : "max-h-0 opacity-0",
				)}
				style={{ transitionProperty: "max-height, opacity" }}
			>
				{expanded && (
					<div className="space-y-3">
						<LessonList
							lessons={module.lessons || []}
							onLessonClick={onLessonClick}
							moduleId={module.id}
						/>
					</div>
				)}
			</div>
		</div>
	);
}

export default OutlineNode;
