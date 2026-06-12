import { createHighlighter } from "shiki"
import { createJavaScriptRegexEngine } from "shiki/engine/javascript"

// Dual Catppuccin flavors: Latte for light, Frappé for dark. Shiki emits both in
// a single pass with defaultColor:"light" — Latte as the normal inline color and
// Frappé as --shiki-dark/--shiki-dark-bg CSS vars. A .dark rule in app.css swaps
// to the dark vars, so light renders exactly as before.
const THEMES = { light: "catppuccin-latte", dark: "catppuccin-frappe" }

// Map common alias/label cases to Shiki language ids. Anything not in this map
// is passed through verbatim (Shiki accepts canonical ids directly).
const LANGUAGE_ALIASES = {
	"c++": "cpp",
	cc: "cpp",
	cxx: "cpp",
	"objective-c": "objc",
	"objective-cpp": "objcpp",
	golang: "go",
	js: "javascript",
	jsx: "tsx",
	ts: "typescript",
	sh: "bash",
	shell: "bash",
	yml: "yaml",
}

const HTML_ESCAPES = {
	"&": "&amp;",
	"<": "&lt;",
	">": "&gt;",
	'"': "&quot;",
	"'": "&#39;",
}

export function escapeHtml(text) {
	return text.replace(/[&<>"']/g, (char) => HTML_ESCAPES[char])
}

export function normalizeLanguage(language) {
	if (!language) return "text"
	const lower = String(language).toLowerCase()
	return LANGUAGE_ALIASES[lower] || lower
}

// Lazy singleton so the engine + theme grammars are downloaded only once on
// first highlight, then reused for every subsequent call.
let highlighterPromise = null

function getHighlighter() {
	if (!highlighterPromise) {
		highlighterPromise = createHighlighter({
			themes: [THEMES.light, THEMES.dark],
			langs: [],
			engine: createJavaScriptRegexEngine(),
		})
	}
	return highlighterPromise
}

async function ensureLanguageLoaded(highlighter, language) {
	if (language === "text" || highlighter.getLoadedLanguages().includes(language)) {
		return language
	}
	// Unknown LLM-generated language ids fall back to plain "text" so the render
	// never breaks; this is the only fallback in the highlight pipeline.
	try {
		await highlighter.loadLanguage(language)
		return language
	} catch {
		return "text"
	}
}

// Dual-theme tokens carry their colors on `htmlStyle` (a { color, --shiki-dark }
// object in Shiki v4) instead of the single `color` string, so flatten it into an
// inline style string the same way Shiki's own HTML renderer does.
function tokenStyle(token) {
	return Object.entries(token.htmlStyle)
		.map(([property, value]) => `${property}:${value}`)
		.join(";")
}

// Full <pre class="shiki"><code>...</code></pre> output. Use for read-only
// surfaces (chat, quizzes, lesson display).
export async function highlightToHtml(code, language) {
	const highlighter = await getHighlighter()
	const lang = await ensureLanguageLoaded(highlighter, normalizeLanguage(language))
	return highlighter.codeToHtml(code, { lang, themes: THEMES, defaultColor: "light" })
}

// Inner colored <span> stream only (no wrapping <pre><code>). Use when the
// caller already owns the <pre> element, e.g. inside react-simple-code-editor.
export async function highlightToInnerHtml(code, language) {
	const highlighter = await getHighlighter()
	const lang = await ensureLanguageLoaded(highlighter, normalizeLanguage(language))
	const { tokens } = highlighter.codeToTokens(code, { lang, themes: THEMES, defaultColor: "light" })
	return tokens
		.map((line) =>
			line.map((token) => `<span style="${tokenStyle(token)}">${escapeHtml(token.content)}</span>`).join("")
		)
		.join("\n")
}
