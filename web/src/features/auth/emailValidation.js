export const isValidEmail = (value) => {
	if (typeof value !== "string") {
		return false
	}

	const trimmed = value.trim()
	if (!trimmed) {
		return false
	}

	const atIndex = trimmed.indexOf("@")
	if (atIndex <= 0) {
		return false
	}

	const dotIndex = trimmed.lastIndexOf(".")
	return dotIndex > atIndex + 1 && dotIndex < trimmed.length - 1
}
