import { compile, run } from "@mdx-js/mdx"
import { useEffect, useState } from "react"
import * as runtime from "react/jsx-runtime"
import rehypeKatex from "rehype-katex"
import remarkGfm from "remark-gfm"
import remarkMath from "remark-math"
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
			<Component />
		</div>
	)
}

export default QuizMarkdown
