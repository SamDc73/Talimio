function TagChip({ tag, contentType }) {
	// Map content types to consistent classes
	const getTagClasses = (type) => {
		switch (type) {
			case "course":
				return "bg-course/10 text-course"
			case "book":
				return "bg-book/10 text-book"
			case "video":
			case "youtube":
				return "bg-video/10 text-video"
			default:
				return "bg-muted text-muted-foreground"
		}
	}

	return <div className={`text-xs font-medium px-2 py-1 rounded-full ${getTagClasses(contentType)}`}>{tag}</div>
}

export default TagChip
