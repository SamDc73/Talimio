import { MdxRenderer } from "./MdxRenderer"

/**
 * Component to render content using MDX
 * @param {Object} props
 * @param {string} props.content - The content to render
 * @returns {JSX.Element}
 */
export function ContentRenderer({ content, lessonId, courseId, lessonConceptId }) {
	// Use MDXRenderer with proper interactive component support
	return <MdxRenderer content={content} lessonId={lessonId} courseId={courseId} lessonConceptId={lessonConceptId} />
}
