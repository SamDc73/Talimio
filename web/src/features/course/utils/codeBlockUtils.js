const LANGUAGE_CLASS_REGEX = /(?:language|lang)[-:]([A-Za-z0-9+#]+)/

export function getLanguage(props, children) {
	if (props?.["data-language"]) {
		return String(props["data-language"]).toLowerCase()
	}

	const queue = []
	if (Array.isArray(children)) {
		queue.push(...children)
	} else if (children != null) {
		queue.push(children)
	}
	while (queue.length > 0) {
		const candidate = queue.shift()
		if (!candidate || typeof candidate !== "object") continue
		const cls = candidate.props?.className ?? candidate.props?.class
		if (typeof cls === "string") {
			const match = cls.match(LANGUAGE_CLASS_REGEX)
			if (match?.[1]) {
				return match[1].toLowerCase()
			}
		}
		const childNodes = candidate.props?.children
		if (Array.isArray(childNodes)) {
			queue.push(...childNodes)
		} else if (childNodes != null) {
			queue.push(childNodes)
		}
	}

	return "text"
}

export function flattenText(node) {
	if (node == null) return ""
	if (typeof node === "string") return node
	if (Array.isArray(node)) return node.map((child) => flattenText(child)).join("")
	if (typeof node === "object" && node?.props) {
		return flattenText(node.props.children)
	}
	return ""
}

function hash32(str) {
	let h = 0
	for (const char of str) {
		const codePoint = char.codePointAt(0)
		if (codePoint === undefined) continue
		h = (h << 5) - h + codePoint
		h = Math.trunc(h)
	}
	return h.toString(16)
}

export function buildStorageKey({ lessonId, language, codeSample }) {
	const snippetSig = hash32((codeSample || "").slice(0, 200))
	return `codeblock:${lessonId || "_"}:${language}:${snippetSig}`
}
