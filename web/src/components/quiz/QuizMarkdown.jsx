import { compile, run } from "@mdx-js/mdx"
import { useEffect, useState } from "react"
import * as runtime from "react/jsx-runtime"
import rehypeKatex from "rehype-katex"
import remarkGfm from "remark-gfm"
import remarkMath from "remark-math"

import { CodeBlockView } from "@/components/CodeBlock"
import logger from "@/lib/logger"

const mdxOptions = {
	outputFormat: "function-body",
	development: false,
	format: "md",
	jsxImportSource: "react",
	jsxRuntime: "automatic",
	providerImportSource: false,
	remarkPlugins: [remarkGfm, remarkMath],
	rehypePlugins: [rehypeKatex],
}

function flattenChildren(children) {
	if (typeof children === "string") return children
	if (Array.isArray(children)) return children.map(flattenChildren).join("")
	if (children && typeof children === "object" && "props" in children) {
		return flattenChildren(children.props?.children)
	}
	return children == null ? "" : String(children)
}

function extractLanguage(className) {
	const match = (className || "").match(/language-(\S+)/)
	return match ? match[1] : "text"
}

// Defined at module scope so the same reference is passed to every render,
// avoiding unnecessary re-renders of the compiled MDX component.
const QUIZ_MDX_COMPONENTS = {
	pre: function QuizPre({ children }) {
		return children
	},
	code: function QuizCode({ className, children, ...props }) {
		const isBlock = typeof className === "string" && className.startsWith("language-")
		if (!isBlock) {
			return (
				<code className="px-1.5 py-0.5 rounded-sm bg-muted text-sm font-mono text-foreground" {...props}>
					{children}
				</code>
			)
		}
		return (
			<CodeBlockView
				code={flattenChildren(children)}
				language={extractLanguage(className)}
				className="my-4 rounded-lg"
			/>
		)
	},
}

export function QuizMarkdown({ content, className }) {
	const [Component, setComponent] = useState(null)

	useEffect(() => {
		let cancelled = false

		if (!content || typeof content !== "string") {
			setComponent(null)
			return () => {
				cancelled = true
			}
		}

		setComponent(null)

		const compileContent = async () => {
			try {
				const compiled = await compile(content, mdxOptions)
				const mdxModule = await run(String(compiled), { ...runtime, baseUrl: import.meta.url })

				if (!cancelled) {
					setComponent(() => mdxModule.default)
				}
			} catch (error) {
				logger.error("Failed to compile quiz markdown", error)
				if (!cancelled) {
					setComponent(null)
				}
			}
		}

		compileContent()

		return () => {
			cancelled = true
		}
	}, [content])

	if (!content) {
		return null
	}

	if (typeof content !== "string") {
		return <div className={className}>{content}</div>
	}

	if (!Component) {
		return <div className={className}>{content}</div>
	}

	return (
		<div className={className}>
			<Component components={QUIZ_MDX_COMPONENTS} />
		</div>
	)
}

// biome-ignore lint/style/useComponentExportOnlyModules: this file keeps the named and default component export together for existing quiz imports.
export default QuizMarkdown
