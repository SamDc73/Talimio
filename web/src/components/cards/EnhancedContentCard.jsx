import { ContentProgressBar } from "@/components/progress/ProgressBar";
import { useProgress } from "@/hooks/useProgress";
import { BaseCard } from "./BaseCard";

/**
 * Content card with progressive enhancement for progress loading
 * Starts with static data, enhances with live progress
 */
export function EnhancedContentCard({
	id,
	title,
	description,
	type,
	staticProgress = 0,
	tags = [],
	...props
}) {
	const { data: liveProgress, isLoading } = useProgress([id]);
	const progress = liveProgress?.[id] ?? staticProgress;

	return (
		<BaseCard {...props}>
			<div className="space-y-4">
				{/* Content type badge */}
				<div className="flex items-center justify-between">
					<span
						className={`
            inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium
            ${type === "course" ? "bg-teal-50 text-teal-600" : ""}
            ${type === "book" ? "bg-blue-50 text-blue-600" : ""}
            ${type === "youtube" ? "bg-violet-50 text-violet-600" : ""}
            ${type === "flashcards" ? "bg-amber-50 text-amber-600" : ""}
          `}
					>
						{type}
					</span>
				</div>

				{/* Title and description */}
				<div>
					<h3 className="text-lg font-semibold text-gray-900 mb-1">{title}</h3>
					{description && (
						<p className="text-sm text-gray-600 line-clamp-2">{description}</p>
					)}
				</div>

				{/* Tags */}
				{tags.length > 0 && (
					<div className="flex flex-wrap gap-1">
						{tags.map((tag) => (
							<span
								key={tag}
								className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-gray-100 text-gray-700"
							>
								{tag}
							</span>
						))}
					</div>
				)}

				{/* Progress bar with animation only when not loading */}
				<div className="pt-2">
					<ContentProgressBar progress={progress} loading={isLoading} />
				</div>
			</div>
		</BaseCard>
	);
}
