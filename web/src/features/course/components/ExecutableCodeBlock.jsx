import { languages as CM_LANGS } from "@codemirror/language-data"
import { EditorView } from "@codemirror/view"
import { loadLanguage } from "@uiw/codemirror-extensions-langs"
import CodeMirror from "@uiw/react-codemirror"
import { AlertTriangle, CheckCircle, Play, RotateCcw } from "lucide-react"
import { useEffect, useMemo, useState } from "react"

import { Badge } from "@/components/Badge"
import { Button } from "@/components/Button"
import ErrorBoundary from "@/components/ErrorBoundary"
import { useExecutableCodeBlockState } from "@/features/course/hooks/useExecutableCodeBlockState"
import { flattenText, getLanguage } from "@/features/course/utils/codeBlockUtils"
import logger from "@/lib/logger"
import { cn } from "@/lib/utils"

import { catppuccinLatte, catppuccinLatteColors } from "./catppuccinTheme"

const LANG_EXT_CACHE = new Map()

// CodeMirror repeatedly resets its internal scroller on mount; disable browser anchoring to avoid loops.
const disableScrollAnchoringTheme = EditorView.theme({
	".cm-scroller": { overflowAnchor: "none" },
})

const CODEMIRROR_ALIASES = {
	js: "javascript",
	ts: "typescript",
	py: "python",
	"c++": "cpp",
	"c#": "csharp",
	cs: "csharp",
	yml: "yaml",
	md: "markdown",
	mdx: "markdown",
	rb: "ruby",
	ps: "powershell",
	ps1: "powershell",
	sh: "shell",
	bash: "shell",
	zsh: "shell",
	gql: "graphql",
	docker: "dockerfile",
	kt: "kotlin",
	rs: "rust",
	ini: "ini",
}

function resolveEditorLanguage(rawLanguage) {
	if (!rawLanguage) return null
	const lowered = String(rawLanguage).toLowerCase()
	return CODEMIRROR_ALIASES[lowered] || lowered
}

export default function ExecutableCodeBlock({ children, className, lessonId, courseId, ...props }) {
	const language = getLanguage(props, children)
	const originalCode = flattenText(children)
	const editorLanguage = resolveEditorLanguage(language)

	// Determine if this code block can be executed
	const canRun = Boolean(language)

	const [languageExtensions, setLanguageExtensions] = useState(() => [EditorView.lineWrapping])

	const { code, result, error, isRunning, onRun, onReset, handleCodeChange } = useExecutableCodeBlockState({
		originalCode,
		language,
		runLanguage: language,
		courseId,
		lessonId,
	})

	useEffect(() => {
		let cancelled = false
		const baseExts = [EditorView.lineWrapping]

		async function loadLang() {
			const name = typeof editorLanguage === "string" ? editorLanguage : null
			if (!name) {
				if (!cancelled) setLanguageExtensions(baseExts)
				return
			}
			if (LANG_EXT_CACHE.has(name)) {
				const cached = LANG_EXT_CACHE.get(name)
				if (!cancelled) setLanguageExtensions([...baseExts, cached])
				return
			}
			try {
				let ext = loadLanguage(name)
				if (ext && typeof ext.then === "function") {
					ext = await ext
				}
				if (ext) {
					LANG_EXT_CACHE.set(name, ext)
					if (!cancelled) setLanguageExtensions([...baseExts, ext])
					return
				}
				const lc = name.toLowerCase()
				const candidate = CM_LANGS.find((l) => {
					const lname = (l?.name || "").toLowerCase()
					const aliases = Array.isArray(l?.alias) ? l.alias.map((a) => (a || "").toLowerCase()) : []
					return lname === lc || aliases.includes(lc)
				})
				if (candidate) {
					try {
						let ext2 = candidate.load()
						if (ext2 && typeof ext2.then === "function") ext2 = await ext2
						if (ext2) {
							LANG_EXT_CACHE.set(name, ext2)
							if (!cancelled) setLanguageExtensions([...baseExts, ext2])
							return
						}
					} catch (e2) {
						logger.error("Failed to load fallback language extension", e2, { language: editorLanguage })
					}
				}
			} catch (e) {
				logger.error("Failed to load language extension", e, { language: editorLanguage })
			}
			if (!cancelled) setLanguageExtensions(baseExts)
		}

		loadLang()
		return () => {
			cancelled = true
		}
	}, [editorLanguage])

	const editorExtensions = useMemo(
		() => [disableScrollAnchoringTheme, catppuccinLatte, ...languageExtensions],
		[languageExtensions]
	)

	// Exact border shade from Catppuccin Latte to keep container/header borders in perfect sync
	const borderHex = catppuccinLatteColors.surface1.hex
	const actionGroupClassName =
		"inline-flex items-center overflow-hidden rounded-full border border-border/60 bg-background/60 shadow-xs backdrop-blur-[1px]"
	const actionButtonBaseClass =
		"rounded-none first:rounded-s-full last:rounded-e-full h-8 px-3 flex items-center gap-1.5 text-xs font-semibold tracking-wide text-foreground/80 transition-all duration-200 focus-visible:outline-none focus-visible:ring-0 disabled:text-muted-foreground/70 disabled:hover:bg-transparent"

	const runDisabled = !canRun || isRunning
	const runLabel = !canRun ? "Unavailable" : isRunning ? "Running" : "Run"

	return (
		<div
			className="relative group mb-8 rounded-xl overflow-hidden border bg-card shadow-sm hover:shadow-md transition-all duration-200"
			style={{ borderColor: borderHex }}
		>
			{/* Header */}
			<div
				className="flex items-center justify-between gap-3 px-4 py-2.5 border-b bg-gradient-to-r from-green-500/6 via-muted/45 to-muted/35 backdrop-blur-[1px]"
				style={{ borderBottomColor: borderHex }}
			>
				<div className="flex items-center gap-2.5">
					<Badge
						variant="outline"
						className="group/language relative flex items-center gap-1.5 rounded-full border border-primary/25 bg-gradient-to-r from-primary/8 via-primary/5 to-primary/8 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.24em] text-primary/90 shadow-[0_6px_18px_-12px_RGBA(var(--primary-rgb),0.6)] backdrop-blur-[1px]"
					>
						<span
							className="inline-flex h-1 w-1 rounded-full bg-primary shadow-[0_0_6px_RGBA(var(--primary-rgb),0.35)] transition-transform duration-200 group-hover/language:scale-110"
							aria-hidden="true"
						/>
						<span className="opacity-90">
							{(language && language !== "text" && language !== "plaintext" ? language : "code").toUpperCase()}
						</span>
					</Badge>
				</div>
				<div className={actionGroupClassName}>
					<Button
						type="button"
						onClick={onRun}
						disabled={runDisabled}
						variant="outline"
						size="sm"
						title={!canRun ? "Language not supported yet" : undefined}
						className={cn(
							actionButtonBaseClass,
							"border-primary/60 hover:bg-primary/10",
							runDisabled ? "bg-primary/5 text-muted-foreground/70" : "hover:text-primary"
						)}
					>
						<Play className="h-4 w-4" aria-hidden="true" />
						<span>{runLabel}</span>
					</Button>
					<Button
						type="button"
						onClick={onReset}
						disabled={code === originalCode}
						variant="outline"
						size="sm"
						className={cn(
							actionButtonBaseClass,
							"border-destructive/60 hover:bg-destructive/10",
							code === originalCode ? "text-muted-foreground/70" : "hover:text-destructive"
						)}
					>
						{code === originalCode ? (
							<>
								<CheckCircle className="h-4 w-4" aria-hidden="true" />
								<span>Saved</span>
							</>
						) : (
							<>
								<RotateCcw className="h-4 w-4" aria-hidden="true" />
								<span>Reset</span>
							</>
						)}
					</Button>
				</div>
			</div>
			{/* Code editor - always editable */}
			<div className={`p-4 bg-muted/25 ${className || ""}`} {...props}>
				<ErrorBoundary>
					<CodeMirror
						value={code}
						onChange={handleCodeChange}
						basicSetup={{ lineNumbers: false, foldGutter: false }}
						className="bg-transparent"
						style={{ fontSize: "0.9rem", lineHeight: 1.6 }}
						extensions={editorExtensions}
					/>
				</ErrorBoundary>
			</div>
			{/* Output */}
			{(result || error) && (
				<div className="border-t border-border bg-muted/20 px-4 py-3 space-y-3">
					<div className="space-y-3">
						{error && (
							<div className="rounded-md border p-3 bg-muted/30 border-l-2 border-l-red-500">
								<div className="flex items-center gap-2 text-xs font-semibold text-red-600 mb-2">
									<AlertTriangle className="h-4 w-4" aria-hidden="true" />
									Error
								</div>
								<pre className="text-[12.5px] text-red-700 font-mono whitespace-pre-wrap leading-relaxed">
									{String(error)}
								</pre>
							</div>
						)}
						{result?.stdout && (
							<div className="rounded-md border p-3 bg-muted/30 border-l-2 border-l-green-500">
								<div className="flex items-center gap-2 text-xs font-semibold text-green-600 mb-2">
									<CheckCircle className="w-3.5 h-3.5" aria-hidden="true" />
									Output
								</div>
								<pre className="max-h-56 overflow-auto text-[12.5px] text-foreground/90 font-mono whitespace-pre-wrap leading-relaxed">
									{result.stdout}
								</pre>
							</div>
						)}
						{result?.stderr && (
							<div className="rounded-md border p-3 bg-muted/30 border-l-2 border-l-amber-500">
								<div className="flex items-center gap-2 text-xs font-semibold text-amber-700 mb-2">
									<AlertTriangle className="w-3.5 h-3.5" aria-hidden="true" />
									Warnings
								</div>
								<pre className="max-h-56 overflow-auto text-[12.5px] text-amber-800 font-mono whitespace-pre-wrap leading-relaxed">
									{result.stderr}
								</pre>
							</div>
						)}
						{(result?.time != null || result?.memory != null || result?.status) && (
							<div className="flex items-center gap-4 text-[0.65rem] text-muted-foreground font-mono pt-2 border-t border-border/50">
								{result?.status && (
									<span>
										Status: <span className="text-foreground font-medium">{result.status}</span>
									</span>
								)}
								{result?.time != null && (
									<span>
										Time: <span className="text-foreground font-medium">{result.time}s</span>
									</span>
								)}
								{result?.memory != null && (
									<span>
										Memory: <span className="text-foreground font-medium">{result.memory} KB</span>
									</span>
								)}
							</div>
						)}
					</div>
				</div>
			)}
		</div>
	)
}
