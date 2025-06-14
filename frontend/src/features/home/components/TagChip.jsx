export function TagChip({ tag, colorClass, contentType, className = "" }) {
	// If contentType is provided, use semantic colors
	const getColorClass = () => {
		if (colorClass) return colorClass;

		switch (contentType) {
			case "course":
			case "roadmap":
				return "bg-course/10 text-course-text";
			case "book":
				return "bg-book/10 text-book-text";
			case "video":
			case "youtube":
				return "bg-video/10 text-video-text";
			case "flashcard":
				return "bg-flashcard/10 text-flashcard-text";
			default:
				return "bg-gray-100 text-gray-700";
		}
	};

	return (
		<span
			className={`inline-flex items-center px-2.5 py-1 rounded-md text-xs transition-colors duration-200 ${getColorClass()} ${className}`}
		>
			{tag}
		</span>
	);
}
