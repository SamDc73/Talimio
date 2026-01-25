import { createContext, useContext, useMemo } from "react"

export const PracticeRegistryContext = createContext(null)

export function usePracticeRegistry() {
	const ctx = useContext(PracticeRegistryContext)
	if (!ctx) {
		throw new Error("PracticeRegistryProvider is missing in the tree")
	}
	return ctx
}

export function usePracticeItems({ practiceContext } = {}) {
	const { getItems, version } = usePracticeRegistry()

	// biome-ignore lint/correctness/useExhaustiveDependencies: version triggers re-read (registry mutates in place)
	return useMemo(() => {
		const items = getItems()
		if (!practiceContext) {
			return items
		}
		return items.filter((item) => item.practiceContext === practiceContext)
	}, [getItems, practiceContext, version])
}
