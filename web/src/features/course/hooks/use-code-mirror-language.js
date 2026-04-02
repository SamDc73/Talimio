import { LanguageDescription } from "@codemirror/language"
import { languages as CM_LANGS } from "@codemirror/language-data"
import { EditorView } from "@codemirror/view"
import { useEffect, useMemo, useState } from "react"
import { catppuccinLatte } from "@/features/course/components/catppuccinTheme"

const LANGUAGE_SUPPORT_CACHE = new Map()
const LANGUAGE_PROMISE_CACHE = new Map()
const BASE_EXTENSIONS = [EditorView.lineWrapping]
const EDITOR_THEME = EditorView.theme({ ".cm-scroller": { overflowAnchor: "none" } })
const PLAIN_TEXT_LABELS = new Set(["text", "plaintext"])

function normalizeValue(value) {
	if (typeof value !== "string") return null
	const normalized = value.trim().toLowerCase()
	return normalized || null
}

function normalizeLanguageInput(input) {
	const kind = input?.kind === "filename" || input?.kind === "both" ? input.kind : "label"
	return {
		kind,
		label: normalizeValue(input?.languageLabel),
		filename: normalizeValue(input?.filename),
	}
}

function resolveLanguageDescription(input) {
	const shouldMatchFilename = input.kind === "filename" || input.kind === "both"
	const shouldMatchLabel = input.kind === "label" || input.kind === "both"

	if (shouldMatchFilename && input.filename) {
		const byFilename = LanguageDescription.matchFilename(CM_LANGS, input.filename)
		if (byFilename) {
			return byFilename
		}
	}

	if (shouldMatchLabel && input.label && !PLAIN_TEXT_LABELS.has(input.label)) {
		return LanguageDescription.matchLanguageName(CM_LANGS, input.label)
	}

	return null
}

async function loadLanguageExtension(input) {
	const description = resolveLanguageDescription(input)
	if (!description) {
		return null
	}

	const cacheKey = description.name.toLowerCase()
	if (LANGUAGE_SUPPORT_CACHE.has(cacheKey)) {
		return LANGUAGE_SUPPORT_CACHE.get(cacheKey)
	}
	if (LANGUAGE_PROMISE_CACHE.has(cacheKey)) {
		return LANGUAGE_PROMISE_CACHE.get(cacheKey)
	}

	const pending = description
		.load()
		.then((support) => {
			LANGUAGE_SUPPORT_CACHE.set(cacheKey, support)
			return support
		})
		.finally(() => {
			LANGUAGE_PROMISE_CACHE.delete(cacheKey)
		})

	LANGUAGE_PROMISE_CACHE.set(cacheKey, pending)
	return pending
}

export function useCodeMirrorLanguageExtensions(input) {
	const [langExt, setLangExt] = useState(null)
	const inputKind = input?.kind
	const inputLanguageLabel = input?.languageLabel
	const inputFilename = input?.filename

	const normalizedInput = useMemo(
		() => normalizeLanguageInput({ kind: inputKind, languageLabel: inputLanguageLabel, filename: inputFilename }),
		[inputFilename, inputKind, inputLanguageLabel]
	)

	useEffect(() => {
		let cancelled = false
		loadLanguageExtension(normalizedInput).then((ext) => {
			if (!cancelled) {
				setLangExt(ext)
			}
		})
		return () => {
			cancelled = true
		}
	}, [normalizedInput])

	return useMemo(() => [EDITOR_THEME, catppuccinLatte, ...BASE_EXTENSIONS, ...(langExt ? [langExt] : [])], [langExt])
}
