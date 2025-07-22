const TagChip = ({ tag, contentType }) => (
	<div
		className={`text-xs font-medium px-2 py-1 rounded-full ${
			contentType === "course"
				? "bg-course/10 text-course-text"
				: contentType === "book"
					? "bg-book/10 text-book-text"
					: contentType === "video"
						? "bg-video/10 text-video-text"
						: contentType === "flashcard"
							? "bg-flashcard/10 text-flashcard-text"
							: "bg-muted text-muted-foreground"
		}`}
	>
		{tag}
	</div>
);

export default TagChip;
