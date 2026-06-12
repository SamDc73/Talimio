import { useEffect, useState } from "react"
import Editor from "react-simple-code-editor"
import { escapeHtml, highlightToHtml, highlightToInnerHtml } from "@/lib/shiki"
import { cn } from "@/lib/utils"

/* eslint-disable better-tailwindcss/no-unknown-classes -- shiki, shiki-host, and shiki-editor are Shiki-specific class names used for syntax highlighting theming; they are not Tailwind utilities. */

// Highlights `code` asynchronously via Shiki and returns the inner colored HTML
// (no wrapping <pre><code>). While Shiki is loading or re-tokenizing after a
// keystroke, returns plain escaped HTML so the editor's <pre> always matches
// the textarea character-for-character.
function useHighlightedInnerHtml(code, language) {
	const [html, setHtml] = useState(() => escapeHtml(code))

	useEffect(() => {
		let cancelled = false
		// Show plain escaped text immediately to keep editor pre/textarea in sync
		// during typing; replace with colored tokens when Shiki resolves.
		setHtml(escapeHtml(code))
		const run = async () => {
			try {
				const next = await highlightToInnerHtml(code, language)
				if (!cancelled) setHtml(next)
			} catch {
				// Ignore highlight errors; keep escaped text as fallback
			}
		}
		run()
		return () => {
			cancelled = true
		}
	}, [code, language])

	return html
}

// Highlights `code` asynchronously and returns Shiki's full <pre><code> HTML.
// Returns `null` until the first highlight resolves so the caller can render a
// plain <pre> fallback to avoid layout shift.
function useHighlightedBlockHtml(code, language) {
	const [html, setHtml] = useState(null)

	useEffect(() => {
		let cancelled = false
		const run = async () => {
			try {
				const next = await highlightToHtml(code, language)
				if (!cancelled) setHtml(next)
			} catch {
				// Ignore highlight errors; keep null so caller shows plain fallback
			}
		}
		run()
		return () => {
			cancelled = true
		}
	}, [code, language])

	return html
}

// Read-only highlighted code block. Used by chat assistant, quiz markdown, and
// anywhere lessons render non-executable code.
export function CodeBlockView({ code, language, className }) {
	const html = useHighlightedBlockHtml(code, language)

	if (html === null) {
		return (
			<pre
				className={cn(
					"shiki overflow-x-auto p-4 text-sm font-mono bg-code-surface text-code-foreground rounded",
					className
				)}
			>
				<code>{code}</code>
			</pre>
		)
	}

	return (
		<div
			className={cn("shiki-host [&_pre]:overflow-x-auto [&_pre]:p-4 [&_pre]:text-sm", className)}
			// biome-ignore lint/security/noDangerouslySetInnerHtml: Shiki output is escaped HTML; no user-injected scripts.
			// biome-ignore lint/style/useNamingConvention: __html is React's required key for dangerouslySetInnerHTML.
			dangerouslySetInnerHTML={{ __html: html }}
		/>
	)
}

const EDITOR_STYLE = {
	fontFamily: "ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace",
	fontSize: "0.9rem",
	lineHeight: 1.6,
	caretColor: "var(--color-code-foreground)",
}

// Editable highlighted code block. Used by ExecutableCodeBlock and
// WorkspaceCodeRunner where users edit code before running it.
export function CodeBlockEditor({ value, language, onChange, className }) {
	const innerHtml = useHighlightedInnerHtml(value, language)

	return (
		<Editor
			value={value}
			onValueChange={onChange}
			highlight={() => innerHtml}
			className={cn("shiki-editor text-code-foreground", className)}
			padding={16}
			style={EDITOR_STYLE}
		/>
	)
}
