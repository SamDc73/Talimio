import { MDXProvider } from "@mdx-js/react"
import { FillInTheBlank } from "@/components/quiz/FillInTheBlank"
import { FreeForm } from "@/components/quiz/FreeForm"
import { MultipleChoice } from "@/components/quiz/MultipleChoice"
import { useMdxCompile } from "@/features/course/hooks/use-mdx-compile"
import { JXGBoardPractice } from "./JXGBoardPractice"
import { LatexExpressionPractice } from "./LatexExpressionPractice"
import { WikiReferenceLink } from "./WikiReferenceLink"
import WorkspaceAwareCodeBlock from "./WorkspaceAwareCodeBlock"
import { WorkspaceRegistryProvider } from "./WorkspaceRegistryProvider"

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
				<code className="px-1.5 py-0.5 rounded-sm bg-muted text-sm font-mono text-foreground" {...props}>
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

	// Style links
	a: ({ href, ...props }) => {
		if (typeof href === "string" && href.startsWith("wiki:")) {
			return <WikiReferenceLink href={href} {...props} />
		}
		return <a className="text-primary hover:text-primary/80 underline" href={href} {...props} />
	},

	// Style horizontal rules
	hr: () => <hr className="my-8 border-border" />,

	// Handle checkboxes in task lists
	input: (props) => {
		if (props.type === "checkbox") {
			return (
				<input
					type="checkbox"
					className="mr-2 rounded-sm border-input text-primary focus:ring-ring"
					disabled
					{...props}
				/>
			)
		}
		return <input {...props} />
	},
}
const EMPTY_MDX_COMPONENTS = {}

function buildLessonComponents({ components, courseId, lessonConceptId, lessonId }) {
	return {
		...MDX_COMPONENTS,
		FreeForm: function LessonBoundFreeForm(props) {
			return <FreeForm {...props} courseId={courseId} lessonId={lessonId} lessonConceptId={lessonConceptId} />
		},
		JXGBoard: function LessonBoundJXGBoard(props) {
			return <JXGBoardPractice {...props} courseId={courseId} lessonId={lessonId} lessonConceptId={lessonConceptId} />
		},
		LatexExpression: function LessonBoundLatexExpression(props) {
			return (
				<LatexExpressionPractice {...props} courseId={courseId} lessonId={lessonId} lessonConceptId={lessonConceptId} />
			)
		},
		pre: function LessonBoundCodeBlock(props) {
			return <WorkspaceAwareCodeBlock {...props} lessonId={lessonId} courseId={courseId} />
		},
		...components,
	}
}

export function MdxRenderer({ content, lessonId, courseId, lessonConceptId, components = EMPTY_MDX_COMPONENTS }) {
	const { Component, error, isLoading } = useMdxCompile(content, { lessonId, courseId })
	const componentsWithLesson = buildLessonComponents({ components, courseId, lessonConceptId, lessonId })

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
		<div className="lesson-mdx max-w-none text-foreground">
			<WorkspaceRegistryProvider>
				<MDXProvider components={componentsWithLesson}>
					<Component components={componentsWithLesson} />
				</MDXProvider>
			</WorkspaceRegistryProvider>
		</div>
	)
}

// biome-ignore lint/style/useComponentExportOnlyModules: this file keeps the named and default component export together for existing lesson imports.
export default MdxRenderer
