import { compile, run } from "@mdx-js/mdx"
import React, { useEffect, useState } from "react"
import * as runtime from "react/jsx-runtime"
import rehypeAutolinkHeadings from "rehype-autolink-headings"
import rehypeKatex from "rehype-katex"
import rehypeMdxCodeProps from "rehype-mdx-code-props"
import rehypeSlug from "rehype-slug"
import remarkEmoji from "remark-emoji"
import remarkGfm from "remark-gfm"
import remarkMath from "remark-math"
import logger from "@/lib/logger"

// MDX compilation options
const mdxOptions = {
	outputFormat: "function-body",
	development: false,
	format: "mdx",
	jsxImportSource: "react",
	jsxRuntime: "automatic",
	providerImportSource: false,
	remarkPlugins: [
		remarkGfm, // GitHub Flavored Markdown
		remarkMath, // Math support
		remarkEmoji, // Emoji support
	],
	rehypePlugins: [
		rehypeSlug, // Add IDs to headings
		[rehypeAutolinkHeadings, { behavior: "wrap" }], // Link headings
		rehypeKatex, // Math rendering
		[rehypeMdxCodeProps, { tagName: "pre" }], // Pass code meta as JSX props (must be last)
	],
}

// Restricted runtime globals for security
const runtimeGlobals = {
	...runtime,
	React,
	useState: React.useState,
	useEffect: React.useEffect,
	useRef: React.useRef,
	// Safe utility globals only
	Date,
	Math,
	JSON,
	Object,
	Array,
	// Restricted logger for MDX runtime debugging (integrates with app logging)
	logger: {
		log: (...args) => logger.info("MDX", { args }),
		warn: (...args) => logger.info("MDX Warning", { args }),
		error: (...args) => logger.error("MDX Error", new Error(args.join(" "))),
	},
}

/**
 * Quote unquoted attributes in code fence meta (e.g., file=path → file="path")
 * @param {string} meta - The meta string after the language identifier
 * @returns {string} - Meta with properly quoted attributes
 */
function quoteCodeFenceMeta(meta) {
	if (!meta) return meta
	const leadingWhitespace = meta.match(/^\s+/)?.[0] ?? ""
	const trimmed = meta.trim()
	if (!trimmed) return meta

	const parts = trimmed.split(/\s+/).map((part) => {
		const separatorIndex = part.indexOf("=")
		if (separatorIndex === -1) {
			return part
		}
		const key = part.slice(0, separatorIndex)
		const value = part.slice(separatorIndex + 1)
		if (!value) {
			return part
		}
		if (value.startsWith('"') || value.startsWith("'")) {
			return `${key}=${value}`
		}
		return `${key}="${value}"`
	})

	return `${leadingWhitespace}${parts.join(" ")}`
}

/**
 * Preprocess MDX content to fix common issues
 * @param {string} content - Raw MDX content
 * @returns {string} - Cleaned MDX content
 */
function preprocessMDXContent(content) {
	let processed = content

	// Remove JSX comments {/* ... */}
	processed = processed.replace(/\{\/\*[\s\S]*?\*\/\}/g, "")

	// Remove HTML comments <!-- ... -->
	processed = processed.replace(/<!--[\s\S]*?-->/g, "")

	// Fix code fence meta: quote unquoted attributes (file=path → file="path")
	// This must happen before we protect code blocks
	processed = processed.replace(/^(```\w*)([^\n]*)/gm, (_match, fence, meta) => {
		return fence + quoteCodeFenceMeta(meta)
	})

	// Fix common MDX syntax issues
	// Remove any standalone curly braces that aren't in code blocks
	const codeBlockRegex = /```[\s\S]*?```/g
	const codeBlocks = []
	let codeBlockIndex = 0

	// Temporarily replace code blocks to protect them
	processed = processed.replace(codeBlockRegex, (match) => {
		const placeholder = `__CODE_BLOCK_${codeBlockIndex}__`
		codeBlocks[codeBlockIndex] = match
		codeBlockIndex++
		return placeholder
	})

	// Fix problematic patterns outside of code blocks
	// Remove double slashes that might cause issues (but preserve URLs)
	processed = processed.replace(/([^:])\/\/(?!\s)/g, "$1/ /")

	// Restore code blocks
	codeBlocks.forEach((block, index) => {
		processed = processed.replace(`__CODE_BLOCK_${index}__`, block)
	})

	return processed
}

/**
 * Custom hook for compiling and running MDX content
 * @param {string} content - MDX content to compile
 * @returns {Object} - { Component, error, isLoading }
 */
export function useMdxCompile(content) {
	const [Component, setComponent] = useState(null)
	const [error, setError] = useState(null)
	const [isLoading, setIsLoading] = useState(true)

	useEffect(() => {
		let cancelled = false

		// Skip if no content
		if (!content) {
			setComponent(null)
			setError(null)
			setIsLoading(false)
			return
		}

		// Basic content validation
		if (typeof content !== "string") {
			setError("Content must be a string")
			setComponent(null)
			setIsLoading(false)
			return
		}

		// Preprocess the content to fix common issues
		const processedContent = preprocessMDXContent(content)

		// Compile MDX
		const compileMdx = async () => {
			setIsLoading(true)

			try {
				// Compile MDX to JavaScript (use preprocessed content)
				const compiledCode = await compile(processedContent, mdxOptions)

				// Prepare code with React in scope
				const rawCode = String(compiledCode)
				const codeWithReact = `
					const { React, useState, useEffect, useRef } = arguments[0];
					${rawCode}
				`

				// Run the compiled code
				const mdxModule = await run(codeWithReact, {
					...runtimeGlobals,
					baseUrl: import.meta.url,
				})

				// Create a simple wrapper component
				const MdxComponent = (props) => {
					const ContentComponent = mdxModule.default

					// Merge any exported components with the provided components
					const components = { ...props.components }
					for (const [key, value] of Object.entries(mdxModule)) {
						if (key !== "default" && typeof value === "function") {
							components[key] = value
						}
					}

					return React.createElement(ContentComponent, {
						...props,
						components,
					})
				}

				if (!cancelled) {
					setComponent(() => MdxComponent)
					setError(null)
					setIsLoading(false)
				}
			} catch (err) {
				if (!cancelled) {
					// Simple error handling
					let errorMessage = "Failed to compile MDX content"

					if (err.message) {
						const [maybeLine, maybeColumn] = err.message.split(":")
						const lineNumber = Number.parseInt(maybeLine, 10)
						const columnNumber = Number.parseInt(maybeColumn, 10)

						if (Number.isFinite(lineNumber) && Number.isFinite(columnNumber)) {
							errorMessage = `MDX syntax error at line ${lineNumber}`
						} else {
							errorMessage = err.message.split("\n")[0]
						}
					}

					setError(errorMessage)
					setComponent(null)
					setIsLoading(false)
				}
			}
		}

		compileMdx()

		// Cleanup
		return () => {
			cancelled = true
		}
	}, [content])

	return { Component, error, isLoading }
}
