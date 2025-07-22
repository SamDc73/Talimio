import { clsx } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs) {
	return twMerge(clsx(inputs));
}

/**
 * Simple function to convert markdown to HTML
 * In a real app, you would use a proper markdown parser like marked or remark
 *
 * @param {string} markdown - The markdown content
 * @returns {string} HTML content
 */
export function convertMarkdownToHtml(markdown) {
	if (!markdown) return "";

	// This is a very basic implementation
	// In a real app, use a proper markdown parser
	let html = markdown;

	// Convert headers
	html = html.replace(/^# (.*$)/gm, "<h1>$1</h1>");
	html = html.replace(/^## (.*$)/gm, "<h2>$1</h2>");
	html = html.replace(/^### (.*$)/gm, "<h3>$1</h3>");

	// Convert paragraphs
	html = html.replace(/^\s*(\n)?(.+)/gm, (m) =>
		/<(\/)?(h\d|ul|ol|li|blockquote|pre|img)/.test(m) ? m : `<p>${m}</p>`,
	);

	// Convert bold
	html = html.replace(/\*\*(.*)\*\*/gm, "<strong>$1</strong>");

	// Convert italic
	html = html.replace(/\*(.*)\*/gm, "<em>$1</em>");

	// Convert code blocks
	html = html.replace(/```([^`]+)```/gm, "<pre><code>$1</code></pre>");

	// Convert inline code
	html = html.replace(/`([^`]+)`/gm, "<code>$1</code>");

	// Convert lists
	html = html.replace(/^\s*\*\s*(.*)/gm, "<ul><li>$1</li></ul>");
	html = html.replace(/^\s*\d+\.\s*(.*)/gm, "<ol><li>$1</li></ol>");

	// Fix duplicate list tags
	html = html.replace(/<\/ul><ul>/gm, "");
	html = html.replace(/<\/ol><ol>/gm, "");

	// Convert links
	html = html.replace(
		/\[([^\]]+)\]\(([^)]+)\)/gm,
		'<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>',
	);

	return html;
}
