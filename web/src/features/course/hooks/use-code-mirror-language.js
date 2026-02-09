import { languages as CM_LANGS } from "@codemirror/language-data"
import { EditorView } from "@codemirror/view"
import { loadLanguage } from "@uiw/codemirror-extensions-langs"
import { useEffect, useMemo, useState } from "react"
import { catppuccinLatte } from "@/features/course/components/catppuccinTheme"

const LANGUAGE_CACHE = new Map()
const BASE_EXTENSIONS = [EditorView.lineWrapping]
const EDITOR_THEME = EditorView.theme({ ".cm-scroller": { overflowAnchor: "none" } })

async function loadLanguageExtension(lang) {
	if (!lang) return null
	if (LANGUAGE_CACHE.has(lang)) return LANGUAGE_CACHE.get(lang)

	// Try primary loader
	const ext = await Promise.resolve(loadLanguage(lang))
	if (ext) {
		LANGUAGE_CACHE.set(lang, ext)
		return ext
	}

	// Fallback to codemirror language-data
	const match = CM_LANGS.find((e) => {
		const name = e.name?.toLowerCase()
		const aliases = e.alias?.map((a) => a?.toLowerCase()) || []
		return name === lang || aliases.includes(lang)
	})
	if (match) {
		const fallback = await Promise.resolve(match.load())
		if (fallback) {
			LANGUAGE_CACHE.set(lang, fallback)
			return fallback
		}
	}
	return null
}

export function useCodeMirrorLanguageExtensions(language) {
	const [langExt, setLangExt] = useState(null)
	const target = typeof language === "string" ? language.toLowerCase() : null

	useEffect(() => {
		let cancelled = false
		loadLanguageExtension(target).then((ext) => {
			if (!cancelled) setLangExt(ext)
		})
		return () => {
			cancelled = true
		}
	}, [target])

	return useMemo(() => [EDITOR_THEME, catppuccinLatte, ...BASE_EXTENSIONS, ...(langExt ? [langExt] : [])], [langExt])
}
