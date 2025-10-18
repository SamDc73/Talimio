/**
 * Return a simple rounded percentage label, e.g. "42%".
 */
export function formatProgressText(percentage, _type = "content") {
	const rounded = Math.round(percentage || 0)
	return `${rounded}%`
}
