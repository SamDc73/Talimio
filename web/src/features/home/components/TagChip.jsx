function TagChip({ tag, contentType }) {
	// Map content types to consistent classes
	const getTagClasses = (type) => {
		switch (type) {
			case "course":
				return "bg-teal-50 text-teal-600"
			case "book":
				return "bg-blue-50 text-blue-600"
			case "video":
			case "youtube":
				return "bg-violet-50 text-violet-600"
			case "flashcard":
			case "flashcards":
				return "bg-amber-50 text-amber-600"
			default:
				return "bg-gray-100 text-gray-100-foreground"
		}
	}

	return <div className={`text-xs font-medium px-2 py-1 rounded-full ${getTagClasses(contentType)}`}>{tag}</div>
}

export default TagChip
