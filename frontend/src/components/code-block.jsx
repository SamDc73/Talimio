import copy from "copy-to-clipboard";
import { Check, Copy } from "lucide-react";
import { useRef, useState } from "react";

/**
 * CodeBlock component for syntax highlighting
 * Uses pre-rendered HTML from rehype-pretty-code in MDXRenderer
 * Includes a copy button and language display
 *
 * @param {Object} props
 * @param {string} props.code - The code to highlight
 * @param {string} props.language - The language of the code
 * @param {string} props.className - Additional class names
 * @param {React.ReactNode} props.children - Pre-rendered code content
 * @returns {JSX.Element}
 */
export function CodeBlock({
	code,
	language = "text",
	className = "",
	children,
}) {
	const [copied, setCopied] = useState(false);
	const preRef = useRef(null);

	// Normalize language identifier
	const normalizedLanguage = language.replace(/language-/, "").toLowerCase();

	// Handle copy button click
	const handleCopy = () => {
		// If code prop is provided, use that
		if (code) {
			copy(code);
			setCopied(true);
			setTimeout(() => setCopied(false), 2000);
			return;
		}

		// Otherwise, try to extract text from the pre element
		if (preRef.current) {
			const text = preRef.current.textContent || "";
			copy(text);
			setCopied(true);
			setTimeout(() => setCopied(false), 2000);
		}
	};

	return (
		<div
			className={`relative group rounded-md overflow-hidden mb-4 ${className}`}
		>
			{/* Language badge */}
			<div className="absolute top-0 right-0 bg-zinc-100 text-zinc-700 px-2 py-1 text-xs font-mono rounded-bl-md z-10">
				{normalizedLanguage}
			</div>

			{/* Copy button */}
			<button
				type="button"
				onClick={handleCopy}
				className="absolute top-2 right-12 p-1.5 rounded-md bg-zinc-100 text-zinc-700 opacity-0 group-hover:opacity-100 transition-opacity z-10"
				aria-label={copied ? "Copied!" : "Copy code"}
			>
				{copied ? (
					<Check className="h-4 w-4 text-emerald-600" />
				) : (
					<Copy className="h-4 w-4" />
				)}
			</button>

			{/* Code block */}
			{children ? (
				// If children are provided (pre-rendered HTML), use them
				<div ref={preRef} className="code-block-wrapper">
					{children}
				</div>
			) : (
				// Otherwise, render a simple pre/code block
				<pre
					ref={preRef}
					className="bg-[#eff1f5] p-4 rounded-md overflow-x-auto text-sm font-mono"
				>
					<code className="language-{normalizedLanguage}">{code}</code>
				</pre>
			)}
		</div>
	);
}
