import { evaluate } from "@mdx-js/mdx";
import { MDXProvider } from "@mdx-js/react";
import { useEffect, useMemo, useState } from "react";
import * as runtime from "react/jsx-runtime";
import rehypePrettyCode from "rehype-pretty-code";
import rehypeRaw from "rehype-raw";
import remarkGfm from "remark-gfm";
import remarkRehype from "remark-rehype";
import { CodeBlock } from "../../components/code-block";
import "./LessonViewer.css";

// Configure rehype-pretty-code with Catppuccin Latte theme
const prettyCodeOptions = {
	theme: "catppuccin-latte",
	keepBackground: true,
	defaultLang: "text",
};

/**
 * Component to render MDX/Markdown content using @mdx-js/mdx
 * with custom components to match the styling of the original implementation
 *
 * @param {Object} props
 * @param {string} props.content - The content to render
 * @returns {JSX.Element}
 */
export function MDXRenderer({ content }) {
	const [mdxModule, setMdxModule] = useState(null);
	const [error, setError] = useState(null);

	// Custom components to match the styling of the original implementation
	// Memoize components to avoid unnecessary re-renders
	const components = useMemo(
		() => ({
			// Headings
			h1: (props) => (
				<h1 className="text-3xl font-bold mt-8 mb-4 text-zinc-900" {...props} />
			),
			h2: (props) => (
				<h2
					className="text-2xl font-semibold mt-6 mb-3 text-zinc-900"
					{...props}
				/>
			),
			h3: (props) => (
				<h3
					className="text-xl font-semibold mt-5 mb-2 text-zinc-900"
					{...props}
				/>
			),

			// Text elements
			p: (props) => (
				<p className="mb-4 text-zinc-700 leading-relaxed" {...props} />
			),
			a: (props) => (
				<a
					className="text-emerald-600 hover:text-emerald-700 underline"
					target="_blank"
					rel="noopener noreferrer"
					{...props}
				/>
			),
			strong: (props) => <strong className="font-semibold" {...props} />,
			em: (props) => <em className="italic" {...props} />,

			// Lists
			ul: (props) => (
				<ul className="list-disc pl-6 mb-4 text-zinc-700" {...props} />
			),
			ol: (props) => (
				<ol className="list-decimal pl-6 mb-4 text-zinc-700" {...props} />
			),
			li: (props) => <li className="mb-1" {...props} />,

			// Code
			code: (props) => {
				const isInline = !props.className;
				// For inline code, keep the original styling
				if (isInline) {
					return (
						<code
							className="bg-zinc-100 px-1.5 py-0.5 rounded text-sm font-mono text-zinc-800"
							{...props}
						/>
					);
				}

				// For code blocks, use our CodeBlock component
				const language = props.className
					? props.className.replace(/language-/, "")
					: "text";
				return <CodeBlock code={props.children} language={language} />;
			},

			// Pre - this will receive the rehype-pretty-code output
			pre: (props) => {
				// Extract language from className (e.g., "language-js")
				const className = props.children?.props?.className || "";
				const match = className.match(/language-(\w+)/);
				const language = match ? match[1] : "text";

				// Wrap in our CodeBlock component
				return (
					<CodeBlock language={language} className="rehype-code-block">
						<pre {...props} />
					</CodeBlock>
				);
			},

			// Blockquote
			blockquote: (props) => (
				<blockquote
					className="border-l-4 border-emerald-300 pl-4 italic my-4 text-zinc-600"
					{...props}
				/>
			),
		}),
		[],
	);

	useEffect(() => {
		if (!content) return;

		// Store the current components reference to use in the async function
		const currentComponents = components;

		const compileMdx = async () => {
			try {
				// Evaluate the MDX content with the runtime and rehype plugins
				const result = await evaluate(content, {
					...runtime,
					development: false,
					useMDXComponents: () => currentComponents,
					rehypePlugins: [rehypeRaw, [rehypePrettyCode, prettyCodeOptions]],
					remarkPlugins: [
						remarkGfm,
						[remarkRehype, { allowDangerousHtml: true }],
					],
				});

				setMdxModule(result);
				setError(null);
			} catch (err) {
				console.error("Error compiling MDX:", err);
				setError(err.message);
			}
		};

		compileMdx();
	}, [content, components]);

	if (!content) {
		return <div className="text-gray-500">No content to display</div>;
	}

	if (error) {
		console.warn("MDX rendering error:", error);
		// Fallback to simple text display when MDX fails
		return (
			<div className="markdown-content">
				<div className="text-red-500 mb-4">
					Error rendering content. Displaying plain text version:
				</div>
				<pre className="whitespace-pre-wrap text-zinc-700">{content}</pre>
			</div>
		);
	}

	if (!mdxModule) {
		return <div className="text-gray-500">Loading content...</div>;
	}

	const MDXContent = mdxModule.default;

	try {
		return (
			<div className="markdown-content">
				<MDXProvider components={components}>
					<MDXContent />
				</MDXProvider>
			</div>
		);
	} catch (renderError) {
		console.error("Error during MDX rendering:", renderError);
		// Fallback to simple text display when rendering fails
		return (
			<div className="markdown-content">
				<div className="text-red-500 mb-4">
					Error rendering content. Displaying plain text version:
				</div>
				<pre className="whitespace-pre-wrap text-zinc-700">{content}</pre>
			</div>
		);
	}
}
