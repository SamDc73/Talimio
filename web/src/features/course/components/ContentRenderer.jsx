import { MdxRenderer } from "./MdxRenderer"

/**
 * Component to render content using MDX
 * @param {Object} props
 * @param {string} props.content - The content to render
 * @returns {JSX.Element}
 */
export function ContentRenderer({ content, lessonId, courseId, lessonConceptId }) {
	// Debug logging moved outside render
	if (process.env.NODE_ENV === "development") {
	}

	// Use MDXRenderer with proper interactive component support
	return <MdxRenderer content={content} lessonId={lessonId} courseId={courseId} lessonConceptId={lessonConceptId} />
}
