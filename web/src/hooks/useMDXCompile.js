import { compile, run } from "@mdx-js/mdx"
import React, { useEffect, useState } from "react"
import * as runtime from "react/jsx-runtime"
import rehypeAutolinkHeadings from "rehype-autolink-headings"
import rehypeKatex from "rehype-katex"
import rehypePrettyCode from "rehype-pretty-code"
import rehypeSlug from "rehype-slug"
import remarkEmoji from "remark-emoji"
import remarkGfm from "remark-gfm"
import remarkMath from "remark-math"
import { mdxCache } from "@/lib/mdx-cache"

// Configure rehype-pretty-code
const prettyCodeOptions = {
	theme: "catppuccin-latte",
	keepBackground: true,
	defaultLang: "text",
	onVisitLine(node) {
		if (!node.properties.className) {
			node.properties.className = []
		}
	},
	onVisitHighlightedLine(node) {
		node.properties.className = ["line--highlighted"]
	},
	onVisitHighlightedWord(node) {
		node.properties.className = ["word--highlighted"]
	},
	transformers: [
		{
			pre(node) {
				const codeElement = node.children?.[0]
				if (codeElement?.properties?.["data-language"]) {
					node.properties = node.properties || {}
					node.properties["data-language"] = codeElement.properties["data-language"]
				}
				return node
			},
		},
	],
}

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
		[rehypePrettyCode, prettyCodeOptions], // Syntax highlighting
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

		// Check cache first
		if (mdxCache.has(content)) {
			const cachedComponent = mdxCache.get(content)
			setComponent(() => cachedComponent)
			setError(null)
			setIsLoading(false)
			return
		}

		// Check if already compiling
		if (mdxCache.isCompiling(content)) {
			const compilingPromise = mdxCache.getCompiling(content)
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
		const compileMDX = async () => {
			setIsLoading(true)

			const compilationPromise = (async () => {
				try {
					// Compile MDX to JavaScript
					const compiledCode = await compile(content, mdxOptions)

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
					const MDXComponent = (props) => {
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

					// Cache the component
					mdxCache.set(content, MDXComponent)

					return MDXComponent
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
					mdxCache.compiling.delete(mdxCache.getKey(content))

					if (process.env.NODE_ENV === "development") {
						console.error("[useMDXCompile] Compilation error:", err)
					}

					throw new Error(errorMessage)
				}
			})()

			// Store the compilation promise
			mdxCache.setCompiling(content, compilationPromise)

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

		compileMDX()

		// Cleanup
		return () => {
			cancelled = true
		}
	}, [content])

	return { Component, error, isLoading }
}
