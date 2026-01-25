import { MDXProvider } from "@mdx-js/react"
import { FillInTheBlank } from "@/components/quiz/FillInTheBlank.jsx"
import { FreeForm } from "@/components/quiz/FreeForm.jsx"
import { MultipleChoice } from "@/components/quiz/MultipleChoice.jsx"
import { useMDXCompile } from "@/features/course/hooks/useMDXCompile"
import { LatexExpressionPractice } from "./LatexExpressionPractice.jsx"
import WorkspaceAwareCodeBlock from "./WorkspaceAwareCodeBlock.jsx"
import { WorkspaceRegistryProvider } from "./workspaceContext"

// Static component overrides - defined once outside component
const MDX_COMPONENTS = {
	// Quiz components
	MultipleChoice: MultipleChoice,
	FillInTheBlank: FillInTheBlank,
	FreeForm: FreeForm,

	// Style headings
	h1: (props) => <h1 className="text-3xl font-bold mb-6 mt-8 text-foreground" {...props} />,
	h2: (props) => <h2 className="text-2xl font-semibold mb-4 mt-6 text-foreground" {...props} />,
	h3: (props) => <h3 className="text-xl font-medium mb-3 mt-4 text-foreground" {...props} />,
	h4: (props) => <h4 className="text-lg font-medium mb-2 mt-3 text-foreground" {...props} />,
	h5: (props) => <h5 className="text-base font-medium mb-2 mt-3 text-foreground" {...props} />,
	h6: (props) => <h6 className="text-sm font-medium mb-2 mt-3 text-foreground" {...props} />,

	// Style paragraphs and text
	p: (props) => <p className="mb-4 leading-relaxed text-muted-foreground" {...props} />,
	strong: (props) => <strong className="font-semibold text-foreground" {...props} />,
	em: (props) => <em className="italic" {...props} />,

	// Style lists
	ul: (props) => <ul className="list-disc pl-6 mb-4 space-y-1" {...props} />,
	ol: (props) => <ol className="list-decimal pl-6 mb-4 space-y-1" {...props} />,
	li: (props) => <li className="mb-1 text-muted-foreground" {...props} />,

	// Style code blocks
	code: ({ className, children, ...props }) => {
		const isInline = !className
		if (isInline) {
			return (
				<code className="px-1.5 py-0.5 rounded bg-muted text-sm font-mono text-foreground" {...props}>
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

	// Style blockquotes
	blockquote: (props) => (
		<blockquote
			className="border-l-4 border-completed/40 pl-4 italic my-4 text-muted-foreground bg-completed/10 py-2"
			{...props}
		/>
	),

	// Style tables
	table: (props) => (
		<div className="overflow-x-auto mb-4">
			<table className="min-w-full divide-y divide-border border border-border rounded-lg" {...props} />
		</div>
	),
	thead: (props) => <thead className="bg-muted/40" {...props} />,
	tbody: (props) => <tbody className="bg-card divide-y divide-border" {...props} />,
	th: (props) => (
		<th
			className="px-6 py-3 text-left text-xs font-medium text-muted-foreground/80 uppercase tracking-wider border-b"
			{...props}
		/>
	),
	td: (props) => <td className="px-6 py-4 whitespace-nowrap text-sm text-muted-foreground border-b" {...props} />,

	// Style links
	a: (props) => <a className="text-primary hover:text-primary/80 underline" {...props} />,

	// Style horizontal rules
	hr: () => <hr className="my-8 border-border" />,

	// Handle checkboxes in task lists
	input: (props) => {
		if (props.type === "checkbox") {
			return (
				<input type="checkbox" className="mr-2 rounded border-input text-primary focus:ring-ring" disabled {...props} />
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
 * - Syntax highlighting for code blocks
 * - Math support (LaTeX)
 * - Auto-linking headings
 * - Interactive component support
 */
export function MDXRenderer({ content, lessonId, courseId, lessonConceptId }) {
	// Use the custom hook for all compilation logic
	const { Component, error, isLoading } = useMDXCompile(content, { lessonId, courseId })

	// Render states
	if (!content) {
		return null
	}

	if (error) {
		return (
			<div className="p-4">
				<div className="mb-4 p-4 bg-destructive/10 border-l-4 border-destructive rounded-r-lg">
					<div className="flex">
						<div className="ml-3">
							<h3 className="text-sm font-medium text-destructive">Content Error</h3>
							<div className="mt-2 text-sm text-destructive/90">
								<p>{error}</p>
							</div>
						</div>
					</div>
				</div>

				<details className="mt-4">
					<summary className="cursor-pointer text-sm text-muted-foreground hover:text-foreground font-medium">
						Show raw content for debugging
					</summary>
					<pre className="mt-2 p-3 bg-muted rounded-lg overflow-x-auto text-xs text-foreground border">{content}</pre>
				</details>
			</div>
		)
	}

	if (isLoading) {
		return (
			<div className="text-muted-foreground/80 p-4 text-center" data-askai-exclude="true">
				<div className="animate-pulse">Loading content...</div>
			</div>
		)
	}

	// Render the MDX component
	return (
		<div className="markdown-content prose prose-zinc max-w-none">
			<WorkspaceRegistryProvider>
				{(() => {
					const componentsWithLesson = {
						...MDX_COMPONENTS,
						LatexExpression: (props) => (
							<LatexExpressionPractice
								{...props}
								courseId={courseId}
								lessonId={lessonId}
								lessonConceptId={lessonConceptId}
							/>
						),
						pre: (props) => <WorkspaceAwareCodeBlock {...props} lessonId={lessonId} courseId={courseId} />,
					}
					return (
						<MDXProvider components={componentsWithLesson}>
							<Component components={componentsWithLesson} />
						</MDXProvider>
					)
				})()}
			</WorkspaceRegistryProvider>
		</div>
	)
}

export default MDXRenderer
