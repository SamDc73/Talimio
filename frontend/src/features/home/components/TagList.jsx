import { TagChip } from "./TagChip";

export function TagList({ tags, colorClass, contentType, className = "" }) {
	return (
		<div className={`flex flex-wrap gap-2 mb-4 ${className}`}>
			{tags.slice(0, 3).map((tag) => (
				<TagChip
					key={tag}
					tag={tag}
					colorClass={colorClass}
					contentType={contentType}
				/>
			))}
			{tags.length > 3 && (
				<span className="inline-flex items-center px-2.5 py-1 rounded-md text-xs bg-muted text-muted-foreground">
					+{tags.length - 3}
				</span>
			)}
		</div>
	);
}
