import { compile, run } from "@mdx-js/mdx"
import React, { useEffect, useState } from "react"
import * as runtime from "react/jsx-runtime"
import rehypeAutolinkHeadings from "rehype-autolink-headings"
import rehypeKatex from "rehype-katex"
import rehypeSlug from "rehype-slug"
import remarkEmoji from "remark-emoji"
import remarkGfm from "remark-gfm"
import remarkMath from "remark-math"
import { mdxCache } from "@/lib/mdx-cache"


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
	// Restricted console for debugging
	console: {
		log: console.log,
		warn: console.warn,
		error: console.error,
	},
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

	// Fix self-closing tags that might have issues
	// Match tags like <br/> and ensure they have proper spacing
	processed = processed.replace(/<(\w+)([^>]*?)\/>/g, (_match, tag, attrs) => {
		// Ensure there's a space before the closing slash
		const cleanAttrs = attrs.trim()
		if (cleanAttrs) {
			return `<${tag} ${cleanAttrs} />`
		}
		return `<${tag} />`
	})

	// Remove HTML comments <!-- ... -->
	processed = processed.replace(/<!--[\s\S]*?-->/g, "")

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
export function useMDXCompile(content) {
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

		// Check cache first (use processed content as key)
		if (mdxCache.has(processedContent)) {
			const cachedComponent = mdxCache.get(processedContent)
			setComponent(() => cachedComponent)
			setError(null)
			setIsLoading(false)
			return
		}

		// Check if already compiling
		if (mdxCache.isCompiling(processedContent)) {
			const compilingPromise = mdxCache.getCompiling(processedContent)
			compilingPromise
				.then((result) => {
					if (!cancelled) {
						setComponent(() => result)
						setError(null)
						setIsLoading(false)
					}
					return result
				})
				.catch((err) => {
					if (!cancelled) {
						setError(err.message || "Failed to compile MDX content")
						setComponent(null)
						setIsLoading(false)
					}
				})
			return
		}

		// Compile MDX
		const compileMdx = async () => {
			setIsLoading(true)

			const compilationPromise = (async () => {
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

					// Cache the component (use processedContent as key)
					mdxCache.set(processedContent, MdxComponent)

					return MdxComponent
				} catch (err) {
					// Simple error handling
					let errorMessage = "Failed to compile MDX content"

					if (err.message) {
						const lineMatch = err.message.match(/(\d+):(\d+)/)
						if (lineMatch) {
							errorMessage = `MDX syntax error at line ${lineMatch[1]}`
						} else {
							errorMessage = err.message.split("\n")[0]
						}
					}

					// Clear from compiling cache on error
					mdxCache.compiling.delete(mdxCache.getKey(processedContent))

					if (process.env.NODE_ENV === "development") {
					}

					throw new Error(errorMessage)
				}
			})()

			// Store the compilation promise
			mdxCache.setCompiling(processedContent, compilationPromise)

			// Handle the promise
			compilationPromise
				.then((compiledComponent) => {
					if (!cancelled) {
						setComponent(() => compiledComponent)
						setError(null)
						setIsLoading(false)
					}
					return compiledComponent
				})
				.catch((err) => {
					if (!cancelled) {
						setError(err.message || "Failed to compile MDX content")
						setComponent(null)
						setIsLoading(false)
					}
				})
		}

		compileMdx()

		// Cleanup
		return () => {
			cancelled = true
		}
	}, [content])

	return { Component, error, isLoading }
}
