import { MDXRenderer } from "./MDXRenderer"

/**
 * Component to render content using MDX
 *
 * @param {Object} props
 * @param {string} props.content - The content to render
 * @returns {JSX.Element}
 */
export function ContentRenderer({ content }) {
	// Debug logging moved outside render
	if (process.env.NODE_ENV === "development") {
		console.log("[ContentRenderer] Rendering with content:", {
			contentLength: content?.length || 0,
			contentType: typeof content,
			contentPreview: content?.substring(0, 100),
			hasContent: !!content,
		})
	}

	// Use MDXRenderer with proper interactive component support
	return <MDXRenderer content={content} />
}
