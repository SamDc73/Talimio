import { useCallback, useRef, useState } from "react"
import { PracticeRegistryContext } from "@/features/course/hooks/use-practice-registry"

const normalizeHints = (hints) => {
	if (!hints) {
		return []
	}
	if (Array.isArray(hints)) {
		return hints.filter(Boolean).map(String)
	}
	return [String(hints)]
}

const serializeValue = (value) => {
	if (value === undefined || value === null) {
		return ""
	}
	if (typeof value === "string") {
		return value
	}
	try {
		return JSON.stringify(value)
	} catch {
		return String(value)
	}
}

const areArraysEqual = (left, right) => {
	if (left === right) {
		return true
	}
	if (!Array.isArray(left) || !Array.isArray(right)) {
		return false
	}
	if (left.length !== right.length) {
		return false
	}
	for (let i = 0; i < left.length; i += 1) {
		if (left[i] !== right[i]) {
			return false
		}
	}
	return true
}

const areItemsEqual = (prev, next) => {
	if (!prev || !next) {
		return false
	}
	return (
		prev.question === next.question &&
		prev.expectedLatex === next.expectedLatex &&
		prev.criteriaKey === next.criteriaKey &&
		prev.solutionLatex === next.solutionLatex &&
		prev.solutionMdx === next.solutionMdx &&
		prev.practiceContext === next.practiceContext &&
		prev.conceptId === next.conceptId &&
		prev.courseId === next.courseId &&
		prev.lessonId === next.lessonId &&
		areArraysEqual(prev.hints, next.hints)
	)
}

export function PracticeRegistryProvider({ children }) {
	const registryRef = useRef(new Map())
	const [version, setVersion] = useState(0)

	const registerItem = useCallback((item) => {
		if (!item?.id) {
			return
		}

		const normalized = {
			id: String(item.id),
			question: item.question ?? "",
			expectedLatex: item.expectedLatex ?? "",
			criteria: item.criteria ?? null,
			criteriaKey: serializeValue(item.criteria),
			hints: normalizeHints(item.hints),
			solutionLatex: item.solutionLatex ?? null,
			solutionMdx: item.solutionMdx ?? null,
			practiceContext: item.practiceContext ?? "inline",
			conceptId: item.conceptId ?? null,
			courseId: item.courseId ?? null,
			lessonId: item.lessonId ?? null,
		}

		const registry = registryRef.current
		const prev = registry.get(normalized.id)
		if (!prev || !areItemsEqual(prev, normalized)) {
			registry.set(normalized.id, normalized)
			setVersion((value) => value + 1)
		}
	}, [])

	const unregisterItem = useCallback((id) => {
		if (!id) {
			return
		}
		const registry = registryRef.current
		const removed = registry.delete(String(id))
		if (removed) {
			setVersion((value) => value + 1)
		}
	}, [])

	const getItems = useCallback(() => [...registryRef.current.values()], [])

	return (
		<PracticeRegistryContext.Provider value={{ registerItem, unregisterItem, getItems, version }}>
			{children}
		</PracticeRegistryContext.Provider>
	)
}

export default PracticeRegistryProvider
