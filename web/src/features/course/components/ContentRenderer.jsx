import { MDXRenderer } from "./MDXRenderer";

/**
 * Component to render content using MDX
 *
 * @param {Object} props
 * @param {string} props.content - The content to render
 * @returns {JSX.Element}
 */
export function ContentRenderer({ content }) {
	return <MDXRenderer content={content} />;
}
