import { MDXProvider } from "@mdx-js/react"
import React from "react"
import { FillInTheBlank, FreeForm, MultipleChoice } from "@/components/quiz/index.js"
import { useMDXCompile } from "@/hooks/useMDXCompile"

// Code block component with language display
function CodeBlock({ children, className, ...props }) {
	// Extract language from data-language attribute (rehype-pretty-code provides this reliably)
	const language = props["data-language"] || "text"

	// Only show language badge if it's not plain text
	const showLanguage = language && language !== "text" && language !== "plaintext"

	return (
		<div className="relative group mb-4 rounded-lg overflow-hidden bg-gray-900">
			{/* Language badge */}
			{showLanguage && (
				<div className="absolute top-0 right-0 px-2 py-1 text-xs font-mono text-gray-400 bg-gray-800 rounded-bl-md z-10">
					{language}
				</div>
			)}

			<pre className={`overflow-x-auto p-4 text-gray-100 text-sm font-mono ${className || ""}`} {...props}>
				{children}
			</pre>
		</div>
	)
}

// Static component overrides - defined once outside component
const MDX_COMPONENTS = {
	// Provide React and hooks for interactive components
	React: React,
	useState: React.useState,
	useEffect: React.useEffect,
	useRef: React.useRef,

	// Quiz components
	MultipleChoice: MultipleChoice,
	FillInTheBlank: FillInTheBlank,
	FreeForm: FreeForm,

	// Style headings
	h1: (props) => <h1 className="text-3xl font-bold mb-6 mt-8 text-zinc-900" {...props} />,
	h2: (props) => <h2 className="text-2xl font-semibold mb-4 mt-6 text-zinc-900" {...props} />,
	h3: (props) => <h3 className="text-xl font-medium mb-3 mt-4 text-zinc-900" {...props} />,
	h4: (props) => <h4 className="text-lg font-medium mb-2 mt-3 text-zinc-900" {...props} />,
	h5: (props) => <h5 className="text-base font-medium mb-2 mt-3 text-zinc-900" {...props} />,
	h6: (props) => <h6 className="text-sm font-medium mb-2 mt-3 text-zinc-900" {...props} />,

	// Style paragraphs and text
	p: (props) => <p className="mb-4 leading-relaxed text-zinc-700" {...props} />,
	strong: (props) => <strong className="font-semibold text-zinc-900" {...props} />,
	em: (props) => <em className="italic" {...props} />,

	// Style lists
	ul: (props) => <ul className="list-disc pl-6 mb-4 space-y-1" {...props} />,
	ol: (props) => <ol className="list-decimal pl-6 mb-4 space-y-1" {...props} />,
	li: (props) => <li className="mb-1 text-zinc-700" {...props} />,

	// Style code blocks
	code: ({ className, children, ...props }) => {
		const isInline = !className
		if (isInline) {
			return (
				<code className="px-1.5 py-0.5 rounded bg-gray-100 text-sm font-mono text-zinc-800" {...props}>
					{children}
				</code>
			)
		}
		return (
			<code className={className} {...props}>
				{children}
			</code>
		)
	},
	// Handle both figure wrapper and direct pre elements
	figure: ({ children, ...props }) => {
		// Check if this is a rehype-pretty-code figure
		if (props["data-rehype-pretty-code-figure"] !== undefined) {
			// The pre element is inside this figure
			return <div {...props}>{children}</div>
		}
		return <figure {...props}>{children}</figure>
	},
	pre: CodeBlock,

	// Style blockquotes
	blockquote: (props) => (
		<blockquote
			className="border-l-4 border-emerald-300 pl-4 italic my-4 text-zinc-600 bg-emerald-50 py-2"
			{...props}
		/>
	),

	// Style tables
	table: (props) => (
		<div className="overflow-x-auto mb-4">
			<table className="min-w-full divide-y divide-gray-200 border border-gray-200 rounded-lg" {...props} />
		</div>
	),
	thead: (props) => <thead className="bg-gray-50" {...props} />,
	tbody: (props) => <tbody className="bg-white divide-y divide-gray-200" {...props} />,
	th: (props) => (
		<th
			className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider border-b"
			{...props}
		/>
	),
	td: (props) => <td className="px-6 py-4 whitespace-nowrap text-sm text-zinc-700 border-b" {...props} />,

	// Style links
	a: (props) => <a className="text-emerald-600 hover:text-emerald-800 underline" {...props} />,

	// Style horizontal rules
	hr: () => <hr className="my-8 border-gray-200" />,

	// Handle checkboxes in task lists
	input: (props) => {
		if (props.type === "checkbox") {
			return (
				<input
					type="checkbox"
					className="mr-2 rounded border-gray-300 text-emerald-600 focus:ring-emerald-500"
					disabled
					{...props}
				/>
			)
		}
		return <input {...props} />
	},
}

/**
 * MDXRenderer - Simplified MDX renderer for React 19
 *
 * Features:
 * - GitHub Flavored Markdown (tables, task lists, etc.)
 * - Math rendering with KaTeX
 * - Syntax highlighting for code blocks
 * - Emoji support
 * - Auto-linking headings
 * - Interactive component support
 */
export function MDXRenderer({ content }) {
	// Use the custom hook for all compilation logic
	const { Component, error, isLoading } = useMDXCompile(content)

	// Render states
	if (!content) {
		return <div className="text-gray-500 p-4 text-center">No content to display</div>
	}

	if (error) {
		return (
			<div className="p-4">
				<div className="mb-4 p-4 bg-red-50 border-l-4 border-red-400 rounded-r-lg">
					<div className="flex">
						<div className="ml-3">
							<h3 className="text-sm font-medium text-red-800">Content Error</h3>
							<div className="mt-2 text-sm text-red-700">
								<p>{error}</p>
							</div>
						</div>
					</div>
				</div>

				<details className="mt-4">
					<summary className="cursor-pointer text-sm text-gray-600 hover:text-gray-800 font-medium">
						Show raw content for debugging
					</summary>
					<pre className="mt-2 p-3 bg-gray-100 rounded-lg overflow-x-auto text-xs text-gray-700 border">{content}</pre>
				</details>
			</div>
		)
	}

	if (isLoading) {
		return (
			<div className="text-gray-500 p-4 text-center">
				<div className="animate-pulse">Loading content...</div>
			</div>
		)
	}

	// Render the MDX component
	return (
		<div className="markdown-content prose prose-zinc max-w-none">
			<MDXProvider components={MDX_COMPONENTS}>
				<Component components={MDX_COMPONENTS} />
			</MDXProvider>
		</div>
	)
}

export default MDXRenderer
